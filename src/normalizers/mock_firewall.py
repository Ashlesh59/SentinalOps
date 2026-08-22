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

class MockFirewallNormalizer(BaseNormalizer):
    def normalize(self, raw_event: Dict[str, Any], tenant_id: str = "default-tenant") -> NormalizedAlert:
        raw_copy = copy.deepcopy(raw_event)
        
        source_event_id = raw_event.get("fw_rule_id")
        ts_raw = raw_event.get("timestamp")
        
        src_ip = raw_event.get("src")
        src_ip = src_ip.strip().lower() if src_ip else None
        
        dst_ip = raw_event.get("dst")
        dst_ip = dst_ip.strip().lower() if dst_ip else None
        
        domain = raw_event.get("dns_query")
        domain = domain.strip().lower() if domain else None
        
        action = raw_event.get("action", "")
        severity = Severity.LOW if action == "DENY" else Severity.INFO
        
        return NormalizedAlert(
            tenant_id=tenant_id,
            source_event_id=source_event_id,
            timestamp=ts_raw,
            source_type=SourceType.FIREWALL,
            source_vendor="MockVendor",
            source_product="MockFirewall_Gateway",
            category_name=CategoryName.NETWORK_ACTIVITY,
            class_name=ClassName.NETWORK_FLOW,
            alert_type=f"Network Connection {action}",
            severity=severity,
            src_ip=src_ip,
            dst_ip=dst_ip,
            domain=domain,
            message=f"Traffic {action} from {src_ip} to {dst_ip}",
            raw_event=raw_copy
        )
