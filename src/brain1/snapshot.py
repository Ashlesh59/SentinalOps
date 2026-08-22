import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import IncidentModel, IncidentSignalModel, AggregatedSignalModel, CorrelationEdgeModel, AggregatedSignalAlertModel, NormalizedAlertModel
from src.schemas.snapshot import Brain1IncidentSnapshot, SignalSnapshot, EdgeSnapshot

class SnapshotBuilder:
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id

    async def build_snapshot(self, incident_id: uuid.UUID) -> Brain1IncidentSnapshot:
        incident = await self.session.scalar(
            select(IncidentModel)
            .where(IncidentModel.tenant_id == self.tenant_id, IncidentModel.id == incident_id)
        )
        if not incident:
            raise ValueError(f"Incident {incident_id} not found for tenant {self.tenant_id}")

        # Fetch signals
        sig_ids_result = await self.session.scalars(
            select(IncidentSignalModel.aggregated_signal_id)
            .where(IncidentSignalModel.incident_id == incident_id)
        )
        sig_ids = list(sig_ids_result.all())
        
        signals = []
        if sig_ids:
            signals_result = await self.session.scalars(
                select(AggregatedSignalModel)
                .where(AggregatedSignalModel.id.in_(sig_ids))
            )
            for sig in signals_result.all():
                # fetch first normalized alert to get source/category
                norm_alert = await self.session.scalar(
                    select(NormalizedAlertModel)
                    .join(AggregatedSignalAlertModel, AggregatedSignalAlertModel.normalized_alert_id == NormalizedAlertModel.id)
                    .where(AggregatedSignalAlertModel.aggregated_signal_id == sig.id)
                    .limit(1)
                )

                signals.append(SignalSnapshot(
                    signal_id=sig.id,
                    tenant_id=sig.tenant_id,
                    first_seen=sig.first_seen,
                    last_seen=sig.last_seen,
                    occurrence_count=sig.occurrence_count,
                    severity=sig.severity,
                    category=norm_alert.category_name if norm_alert else "UNKNOWN",
                    alert_type=norm_alert.alert_type if norm_alert else "UNKNOWN",
                    source_vendor=norm_alert.source_vendor if norm_alert else "UNKNOWN",
                    source_product=norm_alert.source_product if norm_alert else "UNKNOWN",
                    entities=sig.entities or {}
                ))

        # Fetch edges between these signals
        edges = []
        if sig_ids:
            edges_result = await self.session.scalars(
                select(CorrelationEdgeModel)
                .where(
                    (CorrelationEdgeModel.left_signal_id.in_(sig_ids)) &
                    (CorrelationEdgeModel.right_signal_id.in_(sig_ids))
                )
            )
            for e in edges_result.all():
                edges.append(EdgeSnapshot(
                    left_signal_id=e.left_signal_id,
                    right_signal_id=e.right_signal_id,
                    score=e.score,
                    reasons=e.reasons,
                    rule_version=e.rule_version
                ))

        return Brain1IncidentSnapshot(
            incident_id=incident.id,
            tenant_id=incident.tenant_id,
            incident_key=incident.incident_key,
            status=incident.status,
            incident_type=incident.incident_type,
            first_seen=incident.first_seen,
            last_seen=incident.last_seen,
            severity=incident.severity,
            title=incident.title,
            anchor_entities=incident.anchor_entities,
            correlation_rule_version=incident.correlation_rule_version,
            incident_version=incident.version,
            signals=signals,
            edges=edges
        )
