import uuid
from enum import Enum
from typing import Optional, Any, Dict
from datetime import datetime, timezone
from pydantic import BaseModel, Field, AwareDatetime, field_validator

class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class SourceType(str, Enum):
    XDR = "XDR"
    IAM = "IAM"
    FIREWALL = "FIREWALL"
    SENTINELOPS_CANONICAL = "SENTINELOPS_CANONICAL"
    UNKNOWN = "UNKNOWN"

class CategoryName(str, Enum):
    AUTHENTICATION = "AUTHENTICATION"
    NETWORK_ACTIVITY = "NETWORK_ACTIVITY"
    ENDPOINT_ACTIVITY = "ENDPOINT_ACTIVITY"
    SYSTEM_ACTIVITY = "SYSTEM_ACTIVITY"

class ClassName(str, Enum):
    PROCESS_ACTIVITY = "PROCESS_ACTIVITY"
    USER_SESSION = "USER_SESSION"
    NETWORK_FLOW = "NETWORK_FLOW"
    SYSTEM_LOG = "SYSTEM_LOG"
    UNKNOWN = "UNKNOWN"

class FileHashAlgorithm(str, Enum):
    MD5 = "MD5"
    SHA1 = "SHA1"
    SHA256 = "SHA256"
    SHA512 = "SHA512"
    UNKNOWN = "UNKNOWN"

class NormalizedAlert(BaseModel):
    """
    OCSF-Lite inspired normalized alert schema for SentinelOps Core.
    Represents standardized security evidence.
    """
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="SentinelOps generated alert ID")
    tenant_id: str = Field(..., description="Customer/Tenant isolation boundary identifier")
    source_event_id: str = Field(..., description="Original alert/log ID from source vendor")
    
    timestamp: AwareDatetime = Field(..., description="Event occurrence time (must be timezone-aware)")
    ingested_at: AwareDatetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Time received by SentinelOps in UTC")
    
    source_type: SourceType = Field(..., description="Type of source system")
    source_vendor: str = Field(..., description="Vendor providing the log (e.g. CrowdStrike, Okta)")
    source_product: str = Field(..., description="Product generating the log (e.g. Falcon, PAN-OS)")
    
    category_name: CategoryName = Field(..., description="High-level security behavior domain")
    class_name: ClassName = Field(..., description="Sub-category of security event")
    alert_type: str = Field(..., description="Specific alert name (e.g., 'Suspicious PowerShell')")
    severity: Severity = Field(default=Severity.INFO, description="Alert severity level")
    
    # Observables / Entities
    user: Optional[str] = None
    host: Optional[str] = None
    src_ip: Optional[str] = None
    dst_ip: Optional[str] = None
    domain: Optional[str] = None
    process_name: Optional[str] = None
    command_line: Optional[str] = None
    
    # File evidence
    file_path: Optional[str] = None
    file_hash: Optional[str] = None
    file_hash_algorithm: Optional[FileHashAlgorithm] = None
    
    # Context
    message: Optional[str] = None
    schema_version: str = Field(default="1.0", description="SentinelOps schema version")
    
    # Raw payload copy
    raw_event: Dict[str, Any] = Field(..., description="Unmodified copy of original vendor event payload")

    @field_validator("timestamp", "ingested_at", mode="after")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("Timestamp must be timezone-aware")
        return v
   