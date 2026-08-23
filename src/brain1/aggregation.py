import uuid
import hashlib
from typing import List, Tuple, Dict, Any, Optional
from datetime import timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from src.db.models import NormalizedAlertModel, AggregatedSignalModel, AggregatedSignalAlertModel
from src.brain1.policy import RuleRegistry, AggregationRule

def generate_aggregation_key(alert: NormalizedAlertModel, rule: AggregationRule) -> str:
    components = []
    for field in rule.fields:
        val = getattr(alert, field, "")
        components.append(str(val) if val is not None else "")
    return ":".join(components)

def generate_aggregated_signal_id(tenant_id: str, rule_id: str, rule_version: str, aggregation_key: str, anchor_id: uuid.UUID) -> uuid.UUID:
    canonical_string = f"{tenant_id}:{rule_id}:{rule_version}:{aggregation_key}:{anchor_id}"
    sha256 = hashlib.sha256(canonical_string.encode('utf-8')).digest()
    return uuid.UUID(bytes=sha256[:16])

def max_severity(sev1: str, sev2: str) -> str:
    order = {"INFO": 1, "LOW": 2, "MEDIUM": 3, "HIGH": 4, "CRITICAL": 5}
    s1 = order.get(sev1.upper(), 0)
    s2 = order.get(sev2.upper(), 0)
    return sev1 if s1 >= s2 else sev2

async def process_and_group_alerts(session: AsyncSession, tenant_id: str, alerts: List[NormalizedAlertModel]) -> List[AggregatedSignalModel]:
    """
    Groups alerts, handling late-arrivals via DB lookups and deterministic reconciliation.
    """
    if not alerts:
        return []
    
    modified_signals: Dict[uuid.UUID, AggregatedSignalModel] = {}
    
    for alert in alerts:
        rule = RuleRegistry.get_rule_for_source(alert.source_type)
        agg_key = generate_aggregation_key(alert, rule)
        window = timedelta(minutes=rule.window_minutes)
        
        # Historical Lookup
        result = await session.execute(
            select(AggregatedSignalModel)
            .where(
                AggregatedSignalModel.tenant_id == tenant_id,
                AggregatedSignalModel.aggregation_rule_id == rule.rule_id,
                AggregatedSignalModel.aggregation_key == agg_key,
                AggregatedSignalModel.first_seen <= alert.timestamp + window,
                AggregatedSignalModel.last_seen >= alert.timestamp - window
            )
        )
        candidates = result.scalars().all()
        
        # Include in-memory ones we just made/modified
        in_memory_candidates = [
            sig for sig in modified_signals.values()
            if sig.aggregation_rule_id == rule.rule_id
            and sig.aggregation_key == agg_key
            and sig.first_seen <= alert.timestamp + window
            and sig.last_seen >= alert.timestamp - window
        ]
        
        all_candidates_map = {c.id: c for c in candidates}
        for im_c in in_memory_candidates:
            all_candidates_map[im_c.id] = im_c
            
        # Tiebreaker: first_seen ASC, then creation_anchor_alert_id ASC
        final_candidates = sorted(
            all_candidates_map.values(), 
            key=lambda x: (x.first_seen, str(x.creation_anchor_alert_id))
        )
        
        if not final_candidates:
            # Create new
            agg_id = generate_aggregated_signal_id(tenant_id, rule.rule_id, rule.rule_version, agg_key, alert.id)
            new_sig = AggregatedSignalModel(
                id=agg_id,
                tenant_id=tenant_id,
                aggregation_key=agg_key,
                aggregation_rule_id=rule.rule_id,
                rule_version=rule.rule_version,
                creation_anchor_alert_id=alert.id,
                first_seen=alert.timestamp,
                last_seen=alert.timestamp,
                occurrence_count=1,
                severity=alert.severity,
                entities={}
            )
            session.add(new_sig)
            await session.flush()
            modified_signals[new_sig.id] = new_sig
            link = AggregatedSignalAlertModel(aggregated_signal_id=new_sig.id, normalized_alert_id=alert.id)
            session.add(link)
            
        elif len(final_candidates) == 1:
            # Append
            target_sig = final_candidates[0]
            target_sig.first_seen = min(target_sig.first_seen, alert.timestamp)
            target_sig.last_seen = max(target_sig.last_seen, alert.timestamp)
            target_sig.occurrence_count += 1
            target_sig.severity = max_severity(target_sig.severity, alert.severity)
            await session.flush()
            modified_signals[target_sig.id] = target_sig
            link = AggregatedSignalAlertModel(aggregated_signal_id=target_sig.id, normalized_alert_id=alert.id)
            session.add(link)
            
        else:
            # Deterministic reconcile: Merge all into the deterministically "oldest" signal
            primary_sig = final_candidates[0]
            for other_sig in final_candidates[1:]:
                primary_sig.first_seen = min(primary_sig.first_seen, other_sig.first_seen)
                primary_sig.last_seen = max(primary_sig.last_seen, other_sig.last_seen)
                primary_sig.occurrence_count += other_sig.occurrence_count
                primary_sig.severity = max_severity(primary_sig.severity, other_sig.severity)
                
                await session.execute(
                    update(AggregatedSignalAlertModel)
                    .where(AggregatedSignalAlertModel.aggregated_signal_id == other_sig.id)
                    .values(aggregated_signal_id=primary_sig.id)
                )
                await session.delete(other_sig)
                if other_sig.id in modified_signals:
                    del modified_signals[other_sig.id]
                    
            primary_sig.first_seen = min(primary_sig.first_seen, alert.timestamp)
            primary_sig.last_seen = max(primary_sig.last_seen, alert.timestamp)
            primary_sig.occurrence_count += 1
            primary_sig.severity = max_severity(primary_sig.severity, alert.severity)
            await session.flush()
            modified_signals[primary_sig.id] = primary_sig
            link = AggregatedSignalAlertModel(aggregated_signal_id=primary_sig.id, normalized_alert_id=alert.id)
            session.add(link)
            
    return list(modified_signals.values())
