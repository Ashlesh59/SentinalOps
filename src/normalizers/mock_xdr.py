import copy
from typing import Dict, Any
from src.models.schema import (
    NormalizedAlert,
    Severity,
    SourceType,
    CategoryName,
    ClassName,
    FileHashAlgorithm
)
from src.normalizers.base import BaseNormalizer

class MockXDRNormalizer(BaseNormalizer):
    def normalize(self, raw_event: Dict[str, Any], tenant_id: str = "default-tenant") -> NormalizedAlert:
        raw_copy = copy.deepcopy(raw_event)
        
        # Extract vendor source event id (must exist in payload or raise KeyError/ValueError)
        source_event_id = raw_event.get("event_id")
        
        # Extract raw timestamp value directly without manual parsing/inventing fallbacks
        ts_raw = raw_event.get("detected_at")
        
        # Canonicalization
        user = raw_event.get("username")
        user = user.strip().lower() if user else None
        
        host = raw_event.get("hostname")
        host = host.strip().lower() if host else None
        
        # Severity mapping
        raw_sev = str(raw_event.get("severity", "")).upper()
        severity = Severity.HIGH if raw_sev == "HIGH" else (Severity.CRITICAL if raw_sev == "CRITICAL" else Severity.INFO)
        
        file_hash = raw_event.get("sha256")
        file_hash_algo = FileHashAlgorithm.SHA256 if file_hash else None

        return NormalizedAlert(
            tenant_id=tenant_id,
            source_event_id=source_event_id,
            timestamp=ts_raw,  # Pydantic validates raw string / timezone awareness
            source_type=SourceType.XDR,
            source_vendor="MockVendor",
            source_product="MockXDR_Agent",
            category_name=CategoryName.ENDPOINT_ACTIVITY,
            class_name=ClassName.PROCESS_ACTIVITY,
            alert_type=raw_event.get("detection_name", "Unknown XDR Event"),
            severity=severity,
            user=user,
            host=host,
            process_name=raw_event.get("process_name") or raw_event.get("process_path"),
            command_line=raw_event.get("cmdline"),
            src_ip=raw_event.get("src_ip"),
            dst_ip=raw_event.get("dst_ip"),
            file_hash=file_hash,
            file_hash_algorithm=file_hash_algo,
            message=raw_event.get("description"),
            raw_event=raw_copy
        )
