from typing import List, Dict, Tuple, Any, Set
import uuid
import hashlib
import time
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert

from src.db.models import (
    NormalizedAlertModel,
    AggregatedSignalModel,
    AggregatedSignalAlertModel,
    CorrelationEdgeModel,
    IncidentModel,
    IncidentSignalModel,
    SignalEntityModel
)

from src.brain1.fingerprinting import generate_dedup_fingerprint
from src.brain1.aggregation import process_and_group_alerts
from src.brain1.entities import extract_alert_entities
from src.brain1.correlation import (
    find_candidates, 
    score_pair,
    generate_edge_id
)
from src.brain1.incident import (
    match_incident, 
    extract_anchors, 
    generate_incident_key
)
from src.brain1.state import Brain1State
from src.brain1.policy import CorrelationPolicyResolver
from src.brain1.context import TenantSecurityContextResolver
from src.brain1.metrics import Brain1Metrics

BATCH_LIMIT = 5000

async def run_correlation(session: AsyncSession, tenant_id: str):
    """
    Executes the deterministic incident correlation pipeline for a tenant.
    Uses AT-LEAST-ONCE processing with effectively-once DB effects.
    """
    metrics = Brain1Metrics()
    start_time = time.perf_counter()
    
    # Generate 64-bit advisory lock key
    lock_id = int(hashlib.sha256(tenant_id.encode('utf-8')).hexdigest()[:15], 16)
    
    # We create an explicit nested transaction wrapper.
    # In FastAPI, `session` might already be in an implicit transaction, 
    # but we need to ensure advisory lock is held for the duration of OUR logic.
    # Using `session.begin_nested()` to create a savepoint, but advisory lock 
    # `pg_try_advisory_xact_lock` scopes to the true transaction.
    # We will assume the caller provides a session, and we will execute the lock.
    
    try:
        try:
            lock_res = await session.execute(
                text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
                {"lock_id": lock_id}
            )
            if not lock_res.scalar():
                return {"status": "skipped_locked", "message": "Tenant is currently processing"}
        except Exception as lock_err:
            # Skip advisory locks if running on SQLite or non-PostgreSQL DB
            if "pg_try_advisory_xact_lock" not in str(lock_err).lower() and "no such function" not in str(lock_err).lower():
                raise lock_err

        state = await Brain1State.get_state(session, tenant_id)
        
        # 1. Incremental Fetch
        result = await session.execute(
            select(NormalizedAlertModel)
            .where(
                NormalizedAlertModel.tenant_id == tenant_id,
                (NormalizedAlertModel.ingested_at > state.last_processed_ingested_at) |
                ((NormalizedAlertModel.ingested_at == state.last_processed_ingested_at) & 
                 (NormalizedAlertModel.id > state.last_processed_alert_id))
            )
            .order_by(NormalizedAlertModel.ingested_at.asc(), NormalizedAlertModel.id.asc())
            .limit(BATCH_LIMIT)
        )
        alerts = result.scalars().all()
        
        if not alerts:
            return {"status": "success", "processed_alerts": 0}
            
        metrics.alerts_newly_processed = len(alerts)
            
        # 2. Exact Duplicate Handling (Cross-Batch)
        fingerprints = []
        alert_fp_map = {}
        for a in alerts:
            fp = generate_dedup_fingerprint(a)
            if fp:
                fingerprints.append(fp)
                alert_fp_map[a.id] = fp
                
        unique_alerts = []
        if fingerprints:
            # Bulk fetch existing
            dup_res = await session.execute(
                select(NormalizedAlertModel.id, NormalizedAlertModel.dedup_fingerprint)
                .where(
                    NormalizedAlertModel.tenant_id == tenant_id,
                    NormalizedAlertModel.dedup_fingerprint.in_(fingerprints)
                )
            )
            existing_fps = {row.dedup_fingerprint: row.id for row in dup_res.all()}
            
            # Map batch
            for a in alerts:
                fp = alert_fp_map.get(a.id)
                if fp:
                    if fp in existing_fps:
                        a.duplicate_of_alert_id = existing_fps[fp]
                        a.dedup_fingerprint = fp
                        a.dedup_fingerprint_version = "exact-v1"
                        metrics.duplicates_detected += 1
                        continue
                    else:
                        existing_fps[fp] = a.id
                        a.dedup_fingerprint = fp
                        a.dedup_fingerprint_version = "exact-v1"
                
                unique_alerts.append(a)
        else:
            unique_alerts = alerts
            
        # 3. Repeated Detection Aggregation (Late-Arrival Aware)
        modified_signals = await process_and_group_alerts(session, tenant_id, unique_alerts)
        
        if not modified_signals:
            # Update state and commit if no signals to process
            last_alert = alerts[-1]
            Brain1State.update_state(state, last_alert.ingested_at, last_alert.id, state.correlation_rule_version)
            await session.commit()
            return {"status": "success", "processed_alerts": len(alerts)}
            
        metrics.signals_created = len(modified_signals) # Simplified counting
        
        # 4. Sync Signal Entities
        signal_entities_map = {}
        for sig in modified_signals:
            # Recompute entities from all alerts for this signal
            sig_alerts_res = await session.execute(
                select(NormalizedAlertModel)
                .join(AggregatedSignalAlertModel, AggregatedSignalAlertModel.normalized_alert_id == NormalizedAlertModel.id)
                .where(AggregatedSignalAlertModel.aggregated_signal_id == sig.id)
            )
            sig_alerts = sig_alerts_res.scalars().all()
            
            ents = []
            for sa in sig_alerts:
                ents.extend(extract_alert_entities(sa))
            
            ents = list(set(ents))
            signal_entities_map[sig.id] = ents
            
            # Insert into SignalEntityModel
            for t, v in ents:
                entity_exists = await session.scalar(
                    select(SignalEntityModel.id).where(
                        SignalEntityModel.tenant_id == tenant_id,
                        SignalEntityModel.aggregated_signal_id == sig.id,
                        SignalEntityModel.entity_type == str(t.value),
                        SignalEntityModel.entity_value == v
                    )
                )
                if not entity_exists:
                    session.add(SignalEntityModel(
                        tenant_id=tenant_id,
                        aggregated_signal_id=sig.id,
                        entity_type=str(t.value),
                        entity_value=v,
                        first_seen=sig.first_seen,
                        last_seen=sig.last_seen
                    ))
                
        # 5. Correlation & Candidates
        policy = CorrelationPolicyResolver.resolve(tenant_id)
        context = TenantSecurityContextResolver.resolve(tenant_id)
        
        candidate_edges = []
        incidents_to_create = []
        incidents_to_update = []
        incident_signal_links = []
        
        # Load active incidents
        inc_result = await session.execute(
            select(IncidentModel, IncidentSignalModel.aggregated_signal_id)
            .join(IncidentSignalModel, IncidentModel.id == IncidentSignalModel.incident_id, isouter=True)
            .where(
                IncidentModel.tenant_id == tenant_id,
                IncidentModel.status.in_(["OPEN", "INVESTIGATING"])
            )
        )
        
        incidents_map = {}
        for inc, sig_id in inc_result.all():
            if inc.id not in incidents_map:
                incidents_map[inc.id] = [inc, set()]
            if sig_id:
                incidents_map[inc.id][1].add(sig_id)
                
        active_incidents = list(incidents_map.values())
        
        for sig in sorted(modified_signals, key=lambda x: x.first_seen):
            sig_ents = signal_entities_map.get(sig.id, [])
            cand_ids = await find_candidates(session, sig, sig_ents, policy, context, metrics)
            
            new_edges = []
            if cand_ids:
                # Fetch candidates
                cand_res = await session.execute(
                    select(AggregatedSignalModel)
                    .where(AggregatedSignalModel.id.in_(cand_ids))
                )
                candidates = cand_res.scalars().all()
                
                edges_to_insert = []
                for cand in candidates:
                    cand_ents = signal_entities_map.get(cand.id)
                    if cand_ents is None:
                        cand_ent_res = await session.execute(
                            select(SignalEntityModel)
                            .where(SignalEntityModel.aggregated_signal_id == cand.id)
                        )
                        cand_ents = [(row.entity_type, row.entity_value) for row in cand_ent_res.scalars().all()]
                    
                    score, reasons = score_pair(sig_ents, cand_ents, sig, cand, policy, context)
                    if score >= policy.edge_threshold:
                        edge_id = generate_edge_id(tenant_id, sig.id, cand.id, policy.rule_version)
                        edges_to_insert.append({
                            "id": edge_id,
                            "tenant_id": tenant_id,
                            "left_signal_id": cand.id,
                            "right_signal_id": sig.id,
                            "score": score,
                            "reasons": reasons,
                            "rule_version": policy.rule_version
                        })
                        
                        # We must build a dummy object to pass to match_incident since it's not flushed
                        edge = CorrelationEdgeModel(left_signal_id=cand.id, right_signal_id=sig.id, score=score)
                        new_edges.append(edge)
                        metrics.edges_created += 1

                for edge_data in edges_to_insert:
                    edge_exists = await session.scalar(
                        select(CorrelationEdgeModel.id).where(CorrelationEdgeModel.id == edge_data["id"])
                    )
                    if not edge_exists:
                        session.add(CorrelationEdgeModel(**edge_data))
                        
            # 6. Incident Seeding / Matching
            best_inc = match_incident(sig, sig_ents, new_edges, active_incidents, policy, context)
            
            if best_inc:
                # Transition singleton if needed
                if best_inc.incident_type == "SINGLETON_DETECTION":
                    best_inc.incident_type = "CORRELATED_INCIDENT"
                    
                if sig.severity == "CRITICAL" and best_inc.severity != "CRITICAL":
                    best_inc.severity = "CRITICAL"
                elif sig.severity == "HIGH" and best_inc.severity not in ["HIGH", "CRITICAL"]:
                    best_inc.severity = "HIGH"
                    
                if sig.last_seen > best_inc.last_seen:
                    best_inc.last_seen = sig.last_seen
                    
                incident_signal_links.append((best_inc.id, sig.id))
                metrics.incident_memberships_added += 1
                
                # Update members in active_incidents
                for idx, (inc, members) in enumerate(active_incidents):
                    if inc.id == best_inc.id:
                        members.add(sig.id)
                        break
            else:
                # No match via new edges. Is it already in an incident?
                already_in_inc = None
                for inc, members in active_incidents:
                    if sig.id in members:
                        already_in_inc = inc
                        break
                
                if already_in_inc:
                    # Update existing incident severity/time if needed
                    if sig.severity == "CRITICAL" and already_in_inc.severity != "CRITICAL":
                        already_in_inc.severity = "CRITICAL"
                    elif sig.severity == "HIGH" and already_in_inc.severity not in ["HIGH", "CRITICAL"]:
                        already_in_inc.severity = "HIGH"
                    if sig.last_seen > already_in_inc.last_seen:
                        already_in_inc.last_seen = sig.last_seen
                else:
                    # Not in any incident. Can we seed a new one?
                    if new_edges:
                        anchors = extract_anchors(sig_ents, policy, context)
                        if anchors:
                            # CREATE CORRELATED
                            inc_key = generate_incident_key(tenant_id, policy.rule_version, sig.id)
                            new_inc = IncidentModel(
                                id=uuid.uuid4(),
                                tenant_id=tenant_id,
                                incident_key=inc_key,
                                status="OPEN",
                                incident_type="CORRELATED_INCIDENT",
                                first_seen=sig.first_seen,
                                last_seen=sig.last_seen,
                                severity=sig.severity,
                                title=f"Correlated Incident {inc_key[:8]}",
                                anchor_entities=anchors,
                                correlation_rule_version=policy.rule_version
                            )
                            session.add(new_inc)
                            incident_signal_links.append((new_inc.id, sig.id))
                            metrics.incidents_created += 1
                            
                            members = {sig.id}
                            for e in new_edges:
                                other = e.left_signal_id if e.right_signal_id == sig.id else e.right_signal_id
                                incident_signal_links.append((new_inc.id, other))
                                members.add(other)
                                
                            active_incidents.append((new_inc, members))
                    elif sig.severity == "CRITICAL":
                        # CREATE SINGLETON
                        anchors = extract_anchors(sig_ents, policy, context)
                        inc_key = generate_incident_key(tenant_id, policy.rule_version, sig.id)
                        new_inc = IncidentModel(
                            id=uuid.uuid4(),
                            tenant_id=tenant_id,
                            incident_key=inc_key,
                            status="OPEN",
                            incident_type="SINGLETON_DETECTION",
                            first_seen=sig.first_seen,
                            last_seen=sig.last_seen,
                            severity=sig.severity,
                            title=f"Critical Detection {inc_key[:8]}",
                            anchor_entities=anchors or {},
                            correlation_rule_version=policy.rule_version
                        )
                        session.add(new_inc)
                        incident_signal_links.append((new_inc.id, sig.id))
                        metrics.incidents_created += 1
                        active_incidents.append((new_inc, {sig.id}))
                    
        # Flush pending additions (like new incidents) before inserting links
        await session.flush()
        
        # Insert links
        for inc_id, sig_id in incident_signal_links:
            link_exists = await session.scalar(
                select(IncidentSignalModel.id).where(
                    IncidentSignalModel.incident_id == inc_id,
                    IncidentSignalModel.aggregated_signal_id == sig_id
                )
            )
            if not link_exists:
                session.add(IncidentSignalModel(incident_id=inc_id, aggregated_signal_id=sig_id))
            
        # 7. Update State
        last_alert = alerts[-1]
        Brain1State.update_state(state, last_alert.ingested_at, last_alert.id, policy.rule_version)
        
        # Commit the transaction explicitly
        await session.commit()
        
        metrics.run_duration_ms = (time.perf_counter() - start_time) * 1000
        return {"status": "success", "processed_alerts": len(alerts), "metrics": metrics.__dict__}
        
    except Exception as e:
        await session.rollback()
        raise e
