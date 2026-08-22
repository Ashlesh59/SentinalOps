import uuid
from typing import Optional, List, Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field, AwareDatetime
from src.models.schema import (
    SourceType,
    CategoryName,
    ClassName,
    Severity,
    FileHashAlgorithm
)
from src.models.privacy import PrivacyClass, PrivacyAction

class SafeEvidenceItem(BaseModel):
    """
    Sanitized, AI-safe representation of a single security event.
    Crosses the Model Trust Boundary into Brain 2.
    MUST NOT contain tenant_id, raw source_event_id, internal alert UUIDs, or raw_event.
    """
    evidence_ref: str = Field(..., description="AI-safe evidence citation reference (e.g. EVIDENCE_001)")
    timestamp: AwareDatetime = Field(..., description="Event occurrence time")
    source_type: SourceType = Field(..., description="High-level category of reporting source")
    
    category_name: CategoryName
    class_name: ClassName
    alert_type: str
    severity: Severity
    
    # Sanitized Aliases & Observables
    user: Optional[str] = Field(default=None, description="Package-scoped alias (e.g. USER_001)")
    host: Optional[str] = Field(default=None, description="Package-scoped alias (e.g. HOST_001)")
    src_ip: Optional[str] = Field(default=None, description="Package-scoped alias or indicator (e.g. PRIVATE_IP_001)")
    dst_ip: Optional[str] = Field(default=None, description="Destination IP indicator/alias")
    domain: Optional[str] = Field(default=None, description="Domain indicator")
    process_name: Optional[str] = Field(default=None, description="Process executable identity")
    command_line: Optional[str] = Field(default=None, description="Sanitized command line or <WITHHELD_UNSAFE_TEXT>")
    
    file_path: Optional[str] = Field(default=None, description="Sanitized file path")
    file_hash: Optional[str] = Field(default=None, description="File cryptographic hash")
    file_hash_algorithm: Optional[FileHashAlgorithm] = Field(default=None)
    message: Optional[str] = Field(default=None, description="Sanitized log message or <WITHHELD_UNSAFE_TEXT>")
    
    schema_version: str = Field(default="1.0")

class SafeEvidencePackage(BaseModel):
    """
    Model-facing container delivered to Brain 2 across the AI Trust Boundary.
    Contains ONLY safe evidence items.
    """
    package_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    policy_profile: str = Field(default="STRICT_EXTERNAL")
    evidence_items: List[SafeEvidenceItem] = Field(default_factory=list)

class PackagePrivacyContext(BaseModel):
    """
    LOCAL ONLY: Maintains relationship maps between AI aliases/refs and true internal identities.
    THIS OBJECT MUST NEVER BE SENT TO BRAIN 2.
    """
    package_id: str
    tenant_id: str
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # EVIDENCE_001 -> { "internal_id": uuid, "source_event_id": vendor_id }
    evidence_reference_map: Dict[str, Dict[str, str]] = Field(default_factory=dict)
    
    # USER_001 -> alice@bank.com
    entity_alias_map: Dict[str, str] = Field(default_factory=dict)

class TransformationRecord(BaseModel):
    """LOCAL ONLY: Audit trail entry for a single field transformation."""
    alert_id: str
    field_name: str
    privacy_class: PrivacyClass
    action_taken: PrivacyAction
    output_marker: Optional[str] = None
    reason: str

class TransformationAudit(BaseModel):
    """LOCAL ONLY: Audit container for an entire gateway execution run."""
    package_id: str
    tenant_id: str
    timestamp: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    records: List[TransformationRecord] = Field(default_factory=list)
