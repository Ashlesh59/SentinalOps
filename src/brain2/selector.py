import hashlib
import json
import uuid
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from src.db.models import IncidentModel, IncidentSignalModel, AggregatedSignalModel, CorrelationEdgeModel, SignalEntityModel



class SafeIncidentPackage(BaseModel):
    incident_alias: str
    incident_version: int
    package_fingerprint: str
    
    title: str
    severity: str
    first_seen: str
    last_seen: str
    
    evidence_truncated: bool
    total_evidence_count: int
    selected_evidence_count: int
    omitted_count: int
    
    signals: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class EvidenceSelector:
    """
    Constructs a bounded, deterministic representation of an incident from a snapshot.
    Uses canonical LocalPrivacyGateway.
    """
    MAX_EVIDENCE_ITEMS = 50
    
    def __init__(self, privacy_gateway=None):
        from src.privacy.gateway import LocalPrivacyGateway
        self.privacy_gateway = privacy_gateway or LocalPrivacyGateway()

    async def extract_package(self, snapshot: 'Brain1IncidentSnapshot') -> SafeIncidentPackage:
        from src.models.schema import NormalizedAlert
        from src.privacy.policy import PrivacyPolicy
        
        # 1. Rank signals deterministically (by severity and occurrence count as a proxy for "strongest evidence")
        severity_rank = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        sorted_signals = sorted(
            snapshot.signals,
            key=lambda s: (severity_rank.get(s.severity, 0), s.occurrence_count, str(s.signal_id)),
            reverse=True
        )

        # 2. Truncate
        total_signals = len(sorted_signals)
        truncated = total_signals > self.MAX_EVIDENCE_ITEMS
        selected_signals = sorted_signals[:self.MAX_EVIDENCE_ITEMS]
        omitted_count = max(0, total_signals - self.MAX_EVIDENCE_ITEMS)
        selected_ids = {s.signal_id for s in selected_signals}

        # 3. We must pass the selected signals through LocalPrivacyGateway.
        # But LocalPrivacyGateway expects NormalizedAlert. We will build dummy NormalizedAlerts.
        dummy_alerts = []
        import datetime
        for s in selected_signals:
            # We map entities to NormalizedAlert fields so gateway can tokenize them
            entities = s.entities
            
            # Ensure aware datetime
            ts = s.first_seen if s.first_seen.tzinfo else s.first_seen.replace(tzinfo=datetime.timezone.utc)
            
            # Ensure valid category
            cat = s.category.upper() if s.category else "SYSTEM_ACTIVITY"
            if cat not in ["AUTHENTICATION", "NETWORK_ACTIVITY", "ENDPOINT_ACTIVITY", "SYSTEM_ACTIVITY"]:
                cat = "SYSTEM_ACTIVITY"
                
            alert = NormalizedAlert(
                id=str(s.signal_id),
                raw_event_id=str(s.signal_id), # dummy
                tenant_id=s.tenant_id,
                source_event_id=str(s.signal_id),
                timestamp=ts,
                ingested_at=ts,
                source_type="UNKNOWN",  # dummy alert for privacy gateway only; category is not a valid source_type
                source_vendor=s.source_vendor,
                source_product=s.source_product,
                category_name=cat,
                class_name="UNKNOWN",
                alert_type=s.alert_type,
                severity=s.severity,
                user=entities.get("USER", ""),
                host=entities.get("DEVICE", ""),
                src_ip=entities.get("IP", ""),
                file_hash=entities.get("HASH", ""),
                raw_event={}
            )
            dummy_alerts.append(alert)

        # Run gateway if we have signals
        safe_signals_map = {}
        if dummy_alerts:
            # STRICT_EXTERNAL policy
            safe_package, privacy_context, audit = self.privacy_gateway.process(dummy_alerts, PrivacyPolicy.strict_external())
            for item in safe_package.evidence_items:
                safe_signals_map[item.evidence_ref] = item
                
            # Reverse map internal_id back to evidence_ref for edge resolution
            internal_to_ref = {}
            for ref, ctx in privacy_context.evidence_reference_map.items():
                internal_to_ref[ctx["internal_alert_id"]] = ref
        else:
            internal_to_ref = {}

        # 4. Alias and format signals
        safe_signals = []
        for s in selected_signals:
            ref = internal_to_ref.get(str(s.signal_id))
            if not ref:
                continue
            item = safe_signals_map[ref]
            
            # Format output dictionary
            safe_signals.append({
                "signal_ref": ref,
                "first_seen": s.first_seen.isoformat(),
                "last_seen": s.last_seen.isoformat(),
                "occurrence_count": s.occurrence_count,
                "severity": s.severity,
                # Include sanitized entities explicitly
                "entities": {
                    "USER": item.user,
                    "DEVICE": item.host,
                    "IP": item.src_ip,
                    "HASH": item.file_hash
                }
            })
            
        # 5. Filter edges just for the selected signals
        edges = [e for e in snapshot.edges if e.left_signal_id in selected_ids and e.right_signal_id in selected_ids]
        
        safe_edges = []
        for e in edges:
            safe_edges.append({
                "left_signal_ref": internal_to_ref.get(str(e.left_signal_id)),
                "right_signal_ref": internal_to_ref.get(str(e.right_signal_id)),
                "score": e.score,
                "reasons": e.reasons
            })

        # 6. Generate deterministic fingerprint
        content_hash = hashlib.sha256()
        content_hash.update(str(snapshot.incident_version).encode())
        for s in safe_signals:
            content_hash.update(s["signal_ref"].encode())
        fingerprint = content_hash.hexdigest()[:16]

        return SafeIncidentPackage(
            incident_alias="INCIDENT_PRIMARY",
            incident_version=snapshot.incident_version,
            package_fingerprint=fingerprint,
            title=snapshot.title, # we might want to sanitize this, but leaving as is since title is internal
            severity=snapshot.severity,
            first_seen=snapshot.first_seen.isoformat(),
            last_seen=snapshot.last_seen.isoformat(),
            evidence_truncated=truncated,
            total_evidence_count=total_signals,
            selected_evidence_count=len(safe_signals),
            omitted_count=omitted_count,
            signals=safe_signals,
            edges=safe_edges
        )
