from typing import Dict, List, Set

class AggregationRule:
    def __init__(self, rule_id: str, rule_version: str, fields: List[str], window_minutes: int = 60):
        self.rule_id = rule_id
        self.rule_version = rule_version
        self.fields = fields
        self.window_minutes = window_minutes

class RuleRegistry:
    # MVP Hardcoded Registry
    RULES = {
        "xdr": AggregationRule(
            rule_id="agg-xdr-v1",
            rule_version="v1",
            fields=["tenant_id", "alert_type", "host", "user", "process_name", "file_hash"]
        ),
        "iam": AggregationRule(
            rule_id="agg-iam-v1",
            rule_version="v1",
            fields=["tenant_id", "alert_type", "user", "src_ip"]
        ),
        "fw": AggregationRule(
            rule_id="agg-fw-v1",
            rule_version="v1",
            fields=["tenant_id", "alert_type", "src_ip", "dst_ip", "domain"]
        ),
        "default": AggregationRule(
            rule_id="agg-default-v1",
            rule_version="v1",
            fields=["tenant_id", "alert_type", "user", "host", "src_ip", "domain", "process_name", "file_hash"]
        )
    }

    @classmethod
    def get_rule_for_source(cls, source_type: str) -> AggregationRule:
        return cls.RULES.get(source_type, cls.RULES["default"])


class CorrelationPolicy:
    rule_version: str = "corr-v2"
    candidate_window_seconds: int = 7200 # 2 hours
    edge_threshold: int = 50
    primary_candidate_entities: Set[str] = {"DEVICE", "HASH", "USER"}
    generic_users: Set[str] = {"SYSTEM", "LOCAL SYSTEM", "NETWORK SERVICE", "LOCAL SERVICE", "AUTHORITY\\SYSTEM"}
    temporal_gap_5m_score: int = 15
    temporal_gap_60m_score: int = 5
    weights: Dict[str, int] = {
        "HASH": 50,
        "DEVICE": 40,
        "USER": 25,
        "IP": 15
    }

class CorrelationPolicyResolver:
    @staticmethod
    def resolve(tenant_id: str) -> CorrelationPolicy:
        return CorrelationPolicy()
