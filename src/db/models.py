import enum
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, List

from sqlalchemy import String, Enum as SQLEnum, DateTime, ForeignKey, JSON, Integer, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class ProcessingStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    NORMALIZED = "NORMALIZED"
    NORMALIZATION_FAILED = "NORMALIZATION_FAILED"
    PERSISTENCE_FAILED = "PERSISTENCE_FAILED"

class StorageTier(str, enum.Enum):
    HOT_POSTGRES = "HOT_POSTGRES"
    COLD_OBJECT_STORE = "COLD_OBJECT_STORE"
    ARCHIVED = "ARCHIVED"

class ImportJobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"

class Base(DeclarativeBase):
    pass

# We use JSONType to fallback to JSON if SQLite, or JSONB if PostgreSQL
JSONType = JSON().with_variant(JSONB, "postgresql")

class RawEventModel(Base):
    __tablename__ = "raw_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_vendor: Mapped[str] = mapped_column(String, nullable=False)
    source_product: Mapped[str] = mapped_column(String, nullable=False)
    source_event_id: Mapped[str] = mapped_column(String, nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    processing_status: Mapped[ProcessingStatus] = mapped_column(SQLEnum(ProcessingStatus), nullable=False, default=ProcessingStatus.RECEIVED)
    normalization_error: Mapped[str] = mapped_column(String, nullable=True)
    storage_tier: Mapped[StorageTier] = mapped_column(SQLEnum(StorageTier), nullable=False, default=StorageTier.HOT_POSTGRES)
    external_storage_pointer: Mapped[str] = mapped_column(String, nullable=True)
    raw_payload_sha256: Mapped[str] = mapped_column(String, nullable=True)

class NormalizedAlertModel(Base):
    __tablename__ = "normalized_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    raw_event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_events.id"), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    source_event_id: Mapped[str] = mapped_column(String, nullable=False)
    
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_vendor: Mapped[str] = mapped_column(String, nullable=False)
    source_product: Mapped[str] = mapped_column(String, nullable=False)
    
    category_name: Mapped[str] = mapped_column(String, nullable=False)
    class_name: Mapped[str] = mapped_column(String, nullable=False)
    alert_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    
    user: Mapped[str] = mapped_column(String, nullable=True)
    host: Mapped[str] = mapped_column(String, nullable=True)
    src_ip: Mapped[str] = mapped_column(String, nullable=True)
    dst_ip: Mapped[str] = mapped_column(String, nullable=True)
    domain: Mapped[str] = mapped_column(String, nullable=True)
    process_name: Mapped[str] = mapped_column(String, nullable=True)
    command_line: Mapped[str] = mapped_column(String, nullable=True)
    file_path: Mapped[str] = mapped_column(String, nullable=True)
    file_hash: Mapped[str] = mapped_column(String, nullable=True)
    file_hash_algorithm: Mapped[str] = mapped_column(String, nullable=True)
    message: Mapped[str] = mapped_column(String, nullable=True)
    schema_version: Mapped[str] = mapped_column(String, nullable=False)

    # Phase 4 deduplication tracking
    duplicate_of_alert_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("normalized_alerts.id"), nullable=True)
    dedup_fingerprint: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    dedup_fingerprint_version: Mapped[str | None] = mapped_column(String, nullable=True)

class ImportJobModel(Base):
    __tablename__ = "import_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    
    filename: Mapped[str] = mapped_column(String, nullable=False)
    format: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ImportJobStatus] = mapped_column(SQLEnum(ImportJobStatus), nullable=False, default=ImportJobStatus.PENDING)
    
    records_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_parsed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parse_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    raw_records_stored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    normalized: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    normalization_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unsupported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    
    error_message: Mapped[str] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)



class Brain1ProcessingStateModel(Base):
    __tablename__ = "brain1_processing_state"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False, unique=True)
    last_processed_ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_processed_alert_id: Mapped[uuid.UUID] = mapped_column(String, nullable=False)
    correlation_rule_version: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class SignalEntityModel(Base):
    __tablename__ = "signal_entities"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    aggregated_signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregated_signals.id", ondelete="CASCADE"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_value: Mapped[str] = mapped_column(String, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "aggregated_signal_id", "entity_type", "entity_value", name="uq_signal_entity"),
        Index("ix_signal_entities_lookup", "tenant_id", "entity_type", "entity_value", "last_seen")
    )

class AggregatedSignalModel(Base):
    __tablename__ = "aggregated_signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    aggregation_key: Mapped[str] = mapped_column(String, nullable=False)
    aggregation_rule_id: Mapped[str] = mapped_column(String, nullable=False, default="agg-v1")
    rule_version: Mapped[str] = mapped_column(String, nullable=False)
    creation_anchor_alert_id: Mapped[uuid.UUID] = mapped_column(String, nullable=False)
    
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    entities: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=True)


class AggregatedSignalAlertModel(Base):
    __tablename__ = "aggregated_signal_alerts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    aggregated_signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregated_signals.id", ondelete="CASCADE"), nullable=False)
    normalized_alert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("normalized_alerts.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("aggregated_signal_id", "normalized_alert_id", name="uq_agg_signal_alert"),
    )


class IncidentModel(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    incident_key: Mapped[str] = mapped_column(String, nullable=False)
    
    status: Mapped[str] = mapped_column(String, nullable=False, default="OPEN")
    incident_type: Mapped[str] = mapped_column(String, nullable=False, default="CORRELATED_INCIDENT")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    
    anchor_entities: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    correlation_rule_version: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("tenant_id", "incident_key", name="uq_tenant_incident_key"),
    )


class IncidentSignalModel(Base):
    __tablename__ = "incident_signals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    aggregated_signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregated_signals.id", ondelete="CASCADE"), nullable=False)

    __table_args__ = (
        UniqueConstraint("incident_id", "aggregated_signal_id", name="uq_incident_signal"),
    )


class CorrelationEdgeModel(Base):
    __tablename__ = "correlation_edges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    
    left_signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregated_signals.id", ondelete="CASCADE"), nullable=False)
    right_signal_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("aggregated_signals.id", ondelete="CASCADE"), nullable=False)
    
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reasons: Mapped[Any] = mapped_column(JSONType, nullable=False)
    rule_version: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("left_signal_id", "right_signal_id", "rule_version", name="uq_corr_edge"),
    )


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    STALE = "STALE"
    CANCELLED = "CANCELLED"

class RunStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED_VALIDATION = "FAILED_VALIDATION"
    FAILED_TIMEOUT = "FAILED_TIMEOUT"
    FAILED = "FAILED"

class InvestigationJobModel(Base):
    __tablename__ = "brain2_investigation_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    incident_version: Mapped[int] = mapped_column(Integer, nullable=False)
    safe_package_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    
    status: Mapped[JobStatus] = mapped_column(SQLEnum(JobStatus), nullable=False, default=JobStatus.PENDING)
    worker_id: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class InvestigationRunModel(Base):
    __tablename__ = "brain2_investigation_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brain2_investigation_jobs.id", ondelete="CASCADE"), nullable=False)
    
    provider_name: Mapped[str] = mapped_column(String, nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    brain2_policy_version: Mapped[str] = mapped_column(String, nullable=False)
    
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[RunStatus] = mapped_column(SQLEnum(RunStatus), nullable=False)
    
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

class InvestigationResultModel(Base):
    __tablename__ = "brain2_investigation_results"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brain2_investigation_runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    
    primary_hypothesis: Mapped[str] = mapped_column(String, nullable=False)
    incident_narrative: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    supporting_evidence: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    contradicting_evidence: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    missing_evidence: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    
    recommended_disposition: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recommended_priority: Mapped[str] = mapped_column(String, nullable=False)
    estimated_impact: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    confidence_drivers: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    confidence_reducers: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    
    next_best_actions: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    response_considerations: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    attack_hypotheses: Mapped[Dict[str, Any]] = mapped_column(JSONType, nullable=False)
    limitations: Mapped[str] = mapped_column(String, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
