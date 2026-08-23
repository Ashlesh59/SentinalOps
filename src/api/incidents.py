import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_db
from src.db.models import (
    IncidentModel, 
    CorrelationEdgeModel, 
    IncidentSignalModel, 
    AggregatedSignalModel, 
    AggregatedSignalAlertModel, 
    NormalizedAlertModel, 
    InvestigationJobModel, 
    InvestigationResultModel
)

router = APIRouter()

def format_duration(first_seen, last_seen):
    if not first_seen or not last_seen:
        return "N/A"
    diff = last_seen - first_seen
    seconds = max(0, int(diff.total_seconds()))
    if seconds < 60:
        return f"{max(1, seconds)}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    rem_min = minutes % 60
    return f"{hours}h {rem_min}m"

def get_soc_priority(severity: str) -> str:
    sev = (severity or "").upper()
    if sev == "CRITICAL":
        return "URGENT"
    elif sev == "HIGH":
        return "HIGH"
    elif sev == "MEDIUM":
        return "MEDIUM"
    return "LOW"

@router.get("/incidents")
async def list_incidents(
    tenant_id: str, 
    severity: str = None,
    status: str = None,
    limit: int = Query(50, le=100),
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(IncidentModel).where(IncidentModel.tenant_id == tenant_id)
    if severity:
        stmt = stmt.where(IncidentModel.severity == severity)
    if status:
        stmt = stmt.where(IncidentModel.status == status)
        
    stmt = stmt.order_by(desc(IncidentModel.last_seen)).limit(limit).offset(offset)
    result = await db.execute(stmt)
    incidents = result.scalars().all()
    
    out = []
    for inc in incidents:
        # Check Brain 2 status
        job_stmt = select(InvestigationJobModel).where(InvestigationJobModel.incident_id == inc.id).order_by(desc(InvestigationJobModel.id)).limit(1)
        latest_job = (await db.execute(job_stmt)).scalars().first()
        
        brain2_status = "NONE"
        brain2_stale = False
        if latest_job:
            brain2_status = latest_job.status
            if latest_job.incident_version < inc.version:
                brain2_stale = True

        # Fetch signals for counts & sources
        sig_ids = (await db.execute(select(IncidentSignalModel.aggregated_signal_id).where(IncidentSignalModel.incident_id == inc.id))).scalars().all()
        signals = []
        if sig_ids:
            signals = (await db.execute(select(AggregatedSignalModel).where(AggregatedSignalModel.id.in_(sig_ids)))).scalars().all()

        sources = list(set(s.entities.get("source_product", "UNKNOWN") for s in signals if s.entities)) if signals else []
        evidence_count = sum(s.occurrence_count for s in signals) if signals else 0

        # Short formatted reference (e.g., INC-0042)
        ref_suffix = str(inc.id)[:4].upper()
        reference = f"INC-{ref_suffix}"

        out.append({
            "incident_id": str(inc.id),
            "reference": reference,
            "title": inc.title or f"{inc.severity} Severity Security Incident",
            "incident_type": inc.incident_type,
            "severity": inc.severity,
            "priority": get_soc_priority(inc.severity),
            "status": inc.status,
            "first_seen": inc.first_seen.isoformat() if inc.first_seen else None,
            "last_seen": inc.last_seen.isoformat() if inc.last_seen else None,
            "duration": format_duration(inc.first_seen, inc.last_seen),
            "incident_version": inc.version,
            "anchor_entities": inc.anchor_entities or {},
            "sources": sources,
            "signal_count": len(signals),
            "evidence_count": evidence_count,
            "brain2_status": brain2_status,
            "brain2_stale": brain2_stale
        })
    return out

@router.get("/incidents/{incident_id}")
async def get_incident(incident_id: str, tenant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        inc_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")
        
    stmt = select(IncidentModel).where(IncidentModel.id == inc_uuid, IncidentModel.tenant_id == tenant_id)
    result = await db.execute(stmt)
    inc = result.scalars().first()
    
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    job_stmt = select(InvestigationJobModel).where(InvestigationJobModel.incident_id == inc.id).order_by(desc(InvestigationJobModel.id)).limit(1)
    latest_job = (await db.execute(job_stmt)).scalars().first()
    
    # fetch summary of signals
    sig_ids = (await db.execute(select(IncidentSignalModel.aggregated_signal_id).where(IncidentSignalModel.incident_id == inc.id))).scalars().all()
    signals = []
    sources = []
    if sig_ids:
        signals = (await db.execute(select(AggregatedSignalModel).where(AggregatedSignalModel.id.in_(sig_ids)))).scalars().all()
        alerts_res = await db.execute(
            select(NormalizedAlertModel.source_vendor, NormalizedAlertModel.source_product)
            .join(AggregatedSignalAlertModel, AggregatedSignalAlertModel.normalized_alert_id == NormalizedAlertModel.id)
            .where(AggregatedSignalAlertModel.aggregated_signal_id.in_(sig_ids))
            .distinct()
        )
        sources = [f"{v} {p}".strip() for v, p in alerts_res.all() if v or p]

    evidence_count = sum(s.occurrence_count for s in signals) if signals else 0
    ref_suffix = str(inc.id)[:4].upper()
    reference = f"INC-{ref_suffix}"
        
    return {
        "incident_id": str(inc.id),
        "reference": reference,
        "tenant_id": inc.tenant_id,
        "status": inc.status,
        "incident_type": inc.incident_type,
        "first_seen": inc.first_seen.isoformat() if inc.first_seen else None,
        "last_seen": inc.last_seen.isoformat() if inc.last_seen else None,
        "duration": format_duration(inc.first_seen, inc.last_seen),
        "severity": inc.severity,
        "priority": get_soc_priority(inc.severity),
        "title": inc.title or f"{inc.severity} Security Incident",
        "anchor_entities": inc.anchor_entities or {},
        "correlation_rule_version": inc.correlation_rule_version,
        "incident_version": inc.version,
        "sources": sources,
        "signal_count": len(signals),
        "evidence_count": evidence_count,
        "member_signal_summary": {
            "count": len(signals),
            "sources": sources
        },
        "brain2_status": latest_job.status if latest_job else "NONE",
        "brain2_stale": latest_job.incident_version < inc.version if latest_job else False
    }

@router.get("/incidents/{incident_id}/timeline")
async def get_incident_timeline(incident_id: str, tenant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        inc_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")
        
    inc = (await db.execute(select(IncidentModel).where(IncidentModel.id == inc_uuid, IncidentModel.tenant_id == tenant_id))).scalars().first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    sig_ids = (await db.execute(select(IncidentSignalModel.aggregated_signal_id).where(IncidentSignalModel.incident_id == inc.id))).scalars().all()
    if not sig_ids:
        return []
        
    signals = (await db.execute(
        select(AggregatedSignalModel)
        .where(AggregatedSignalModel.id.in_(sig_ids))
        .order_by(AggregatedSignalModel.first_seen)
    )).scalars().all()
    
    out = []
    for s in signals:
        alert_res = await db.execute(
            select(NormalizedAlertModel)
            .join(AggregatedSignalAlertModel, AggregatedSignalAlertModel.normalized_alert_id == NormalizedAlertModel.id)
            .where(AggregatedSignalAlertModel.aggregated_signal_id == s.id)
            .limit(1)
        )
        alert = alert_res.scalars().first()
        alert_title = alert.alert_type or alert.message or "Suspicious Activity" if alert else "Security Alert"
        source_label = f"{alert.source_vendor} {alert.source_product}" if alert else "Security Log"
        cat = alert.category_name if alert else "DETECTION"

        out.append({
            "timestamp": s.first_seen.isoformat(),
            "category": cat,
            "alert_type": alert_title,
            "severity": s.severity,
            "occurrence_count": s.occurrence_count,
            "source": source_label,
            "entities": s.entities
        })
    return out

@router.get("/incidents/{incident_id}/correlation-explanation")
async def get_incident_explanation(incident_id: str, tenant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        inc_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")
        
    inc = (await db.execute(select(IncidentModel).where(IncidentModel.id == inc_uuid, IncidentModel.tenant_id == tenant_id))).scalars().first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    # Get members
    sig_ids_result = await db.execute(select(IncidentSignalModel.aggregated_signal_id).where(IncidentSignalModel.incident_id == inc.id))
    sig_ids = [row[0] for row in sig_ids_result.all()]
    
    anchors_list = []
    if isinstance(inc.anchor_entities, dict):
        for k, items in inc.anchor_entities.items():
            if isinstance(items, list):
                for v in items:
                    anchors_list.append({"type": k, "value": v})
    
    if not sig_ids:
        return {
            "incident_id": str(inc.id),
            "rule_version": inc.correlation_rule_version,
            "anchors": anchors_list,
            "edges": []
        }
        
    # Get edges between members
    edges_result = await db.execute(
        select(CorrelationEdgeModel)
        .where(CorrelationEdgeModel.left_signal_id.in_(sig_ids))
        .where(CorrelationEdgeModel.right_signal_id.in_(sig_ids))
    )
    edges = edges_result.scalars().all()
    
    return {
        "incident_id": str(inc.id),
        "rule_version": inc.correlation_rule_version,
        "anchors": anchors_list,
        "edges": [
            {
                "left_signal_id": str(e.left_signal_id),
                "right_signal_id": str(e.right_signal_id),
                "score": e.score,
                "reasons": e.reasons
            }
            for e in edges
        ]
    }


@router.get("/incidents/{incident_id}/privacy-preview")
async def get_incident_privacy_preview(incident_id: str, tenant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        inc_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")
        
    inc = (await db.execute(select(IncidentModel).where(IncidentModel.id == inc_uuid, IncidentModel.tenant_id == tenant_id))).scalars().first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    from src.brain1.snapshot import SnapshotBuilder
    from src.brain2.selector import EvidenceSelector
    
    # 1. Build Brain1 Snapshot
    builder = SnapshotBuilder(db, tenant_id)
    try:
        snapshot = await builder.build_snapshot(inc_uuid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    # 2. Convert to SafePackage via Canonical gateway
    selector = EvidenceSelector()
    safe_package = await selector.extract_package(snapshot)
    
    # Count total raw occurrences in snapshot
    total_raw = sum(s.occurrence_count for s in snapshot.signals) if snapshot.signals else len(safe_package.signals)
    
    import os
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    
    out = safe_package.model_dump()
    out["audit_card"] = {
        "provider": "Anthropic (Claude)" if has_key else "MockProvider (Offline / Deterministic)",
        "model": os.environ.get("BRAIN2_MODEL", "claude-3-5-sonnet-20240620"),
        "privacy_profile": "STRICT_EXTERNAL",
        "evidence_exported": len(safe_package.signals),
        "total_raw_telemetry": total_raw,
        "raw_identifiers_detected": 0,
        "internal_uuids_exported": 0,
        "raw_events_exported": 0,
        "package_fingerprint": safe_package.package_fingerprint
    }
    return out

