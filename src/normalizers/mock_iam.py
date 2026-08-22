import copy
from typing import Dict, Any
from src.models.schema import (
    NormalizedAlert,
    Severity,
    SourceType,
    CategoryName,
    ClassName
)
from src.normalizers.base import BaseNormalizer

class MockIAMNormalizer(BaseNormalizer):
    def normalize(self, raw_event: Dict[str, Any], tenant_id: str = "default-tenant") -> NormalizedAlert:
        raw_copy = copy.deepcopy(raw_event)
        
        source_event_id = raw_event.get("log_id")
        ts_raw = raw_event.get("time")
        
        user = raw_event.get("actor_email")
        user = user.strip().lower() if user else None
        
        ip = raw_event.get("source_ip")
        ip = ip.strip().lower() if ip else None
        
        action = raw_event.get("action", "unknown_action")
        severity = Severity.MEDIUM if action == "login_failed" else Severity.INFO
        
        return NormalizedAlert(
            tenant_id=tenant_id,
            source_event_id=source_event_id,
            timestamp=ts_raw,
            source_type=SourceType.IAM,
            source_vendor="MockVendor",
            source_product="MockIAM_Service",
            category_name=CategoryName.AUTHENTICATION,
            class_name=ClassName.USER_SESSION,
            alert_type=action,
            severity=severity,
            user=user,
            src_ip=ip,
            message=f"Authentication event: {action} via {raw_event.get('auth_method', 'unknown')}",
            raw_event=raw_copy
        )
