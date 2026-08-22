from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Dict, Any

from src.db.database import get_db
from src.db.models import (
    NormalizedAlertModel, 
    AggregatedSignalModel, 
    IncidentModel, 
    InvestigationJobModel
)

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])

# Hardcoded tenant for demo per requirements
DEMO_TENANT_ID = "tenant-test"

@router.get("/summary")
async def get_dashboard_summary(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    # 1. Total Normalized Alerts
    alerts_count = await session.scalar(
        select(func.count(NormalizedAlertModel.id))
        .where(NormalizedAlertModel.tenant_id == DEMO_TENANT_ID)
    )

    # 2. Total Analytical Signals
    signals_count = await session.scalar(
        select(func.count(AggregatedSignalModel.id))
        .where(AggregatedSignalModel.tenant_id == DEMO_TENANT_ID)
    )

    # 3. Open Incidents
    open_incidents = await session.scalar(
        select(func.count(IncidentModel.id))
        .where(IncidentModel.tenant_id == DEMO_TENANT_ID)
        .where(IncidentModel.status == "OPEN")
    )

    # 4. Critical Incidents
    critical_incidents = await session.scalar(
        select(func.count(IncidentModel.id))
        .where(IncidentModel.tenant_id == DEMO_TENANT_ID)
        .where(IncidentModel.severity == "CRITICAL")
    )

    # 5. Investigations Status Breakdown
    pending_jobs = await session.scalar(
        select(func.count(InvestigationJobModel.id))
        .where(InvestigationJobModel.tenant_id == DEMO_TENANT_ID)
        .where(InvestigationJobModel.status.in_(["PENDING", "RUNNING"]))
    )
    failed_jobs = await session.scalar(
        select(func.count(InvestigationJobModel.id))
        .where(InvestigationJobModel.tenant_id == DEMO_TENANT_ID)
        .where(InvestigationJobModel.status == "FAILED")
    )
    succeeded_jobs = await session.scalar(
        select(func.count(InvestigationJobModel.id))
        .where(InvestigationJobModel.tenant_id == DEMO_TENANT_ID)
        .where(InvestigationJobModel.status == "SUCCEEDED")
    )

    # 6. High Priority Incidents (HIGH or CRITICAL)
    high_priority = await session.scalar(
        select(func.count(IncidentModel.id))
        .where(IncidentModel.tenant_id == DEMO_TENANT_ID)
        .where(IncidentModel.severity.in_(["HIGH", "CRITICAL"]))
    )

    # 7. Severity Distribution (from incidents)
    sev_dist_result = await session.execute(
        select(IncidentModel.severity, func.count(IncidentModel.id))
        .where(IncidentModel.tenant_id == DEMO_TENANT_ID)
        .group_by(IncidentModel.severity)
    )
    severity_distribution = {row[0]: row[1] for row in sev_dist_result.all()}

    # 8. Source Distribution (from normalized alerts)
    source_dist_result = await session.execute(
        select(NormalizedAlertModel.source_product, func.count(NormalizedAlertModel.id))
        .where(NormalizedAlertModel.tenant_id == DEMO_TENANT_ID)
        .group_by(NormalizedAlertModel.source_product)
    )
    source_distribution = {row[0]: row[1] for row in source_dist_result.all()}

    # 9. Truthful Noise Reduction Calculation
    alerts_total = alerts_count or 0
    signals_total = signals_count or 0
    reduction_pct = 0.0
    if alerts_total > 0:
        reduction_pct = round(max(0.0, (1.0 - (signals_total / alerts_total)) * 100.0), 1)

    return {
        "normalized_alerts": alerts_total,
        "analytical_signals": signals_total,
        "noise_reduction_percent": reduction_pct,
        "open_incidents": open_incidents or 0,
        "critical_incidents": critical_incidents or 0,
        "high_priority_incidents": high_priority or 0,
        "investigations": (pending_jobs or 0) + (failed_jobs or 0) + (succeeded_jobs or 0),
        "investigations_pending": pending_jobs or 0,
        "investigations_failed": failed_jobs or 0,
        "investigations_succeeded": succeeded_jobs or 0,
        "severity_distribution": severity_distribution,
        "source_distribution": source_distribution
    }
