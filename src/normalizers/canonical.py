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

class GenericCanonicalNormalizer(BaseNormalizer):
    """
    Normalizes events that already follow the SentinelOps Canonical format.
    Does not perform fuzzy mapping; expects strictly matching field names.
    """
    def normalize(self, raw_event: Dict[str, Any], tenant_id: str = "default-tenant") -> NormalizedAlert:
        raw_copy = copy.deepcopy(raw_event)
        
        # Exact field names expected
        source_event_id = raw_event.get("source_event_id")
        if not source_event_id:
            raise ValueError("source_event_id is required in Canonical format")
            
        ts_raw = raw_event.get("timestamp")
        
        # Source Information
        vendor = raw_event.get("vendor", "UnknownVendor")
        product = raw_event.get("product", "UnknownProduct")
        
        # Enums parsing safely
        try:
            category_name = CategoryName(raw_event.get("category", "SYSTEM_ACTIVITY").upper())
        except ValueError:
            category_name = CategoryName.SYSTEM_ACTIVITY
            
        try:
            class_name = ClassName(raw_event.get("class_name", "UNKNOWN").upper())
        except ValueError:
            class_name = ClassName.UNKNOWN
            
        try:
            severity = Severity(raw_event.get("severity", "INFO").upper())
        except ValueError:
            severity = Severity.INFO
            
        alert_type = raw_event.get("alert_type", "Canonical Event")
        
        # File Hash
        file_hash_algo = None
        raw_algo = raw_event.get("file_hash_algorithm")
        if raw_algo:
            try:
                file_hash_algo = FileHashAlgorithm(raw_algo.upper())
            except ValueError:
                pass

        return NormalizedAlert(
            tenant_id=tenant_id,
            source_event_id=str(source_event_id),
            timestamp=ts_raw,
            source_type=SourceType.SENTINELOPS_CANONICAL,
            source_vendor=vendor,
            source_product=product,
            category_name=category_name,
            class_name=class_name,
            alert_type=alert_type,
            severity=severity,
            user=raw_event.get("user"),
            host=raw_event.get("host"),
            src_ip=raw_event.get("src_ip"),
            dst_ip=raw_event.get("dst_ip"),
            domain=raw_event.get("domain"),
            process_name=raw_event.get("process_name"),
            command_line=raw_event.get("command_line"),
            file_path=raw_event.get("file_path"),
            file_hash=raw_event.get("file_hash"),
            file_hash_algorithm=file_hash_algo,
            message=raw_event.get("message"),
            raw_event=raw_copy
        )
