import pytest
from src.privacy.gateway import LocalPrivacyGateway
from src.models.schema import NormalizedAlert, SourceType, CategoryName, ClassName, Severity
from src.privacy.policy import PrivacyPolicy
from datetime import datetime, timezone

def test_private_ip_regression_proof():
    gateway = LocalPrivacyGateway()
    
    # Base alert setup
    base_alert = NormalizedAlert(
        tenant_id="T1",
        source_event_id="e1",
        timestamp=datetime.now(timezone.utc),
        source_type=SourceType.XDR,
        source_vendor="V",
        source_product="P",
        category_name=CategoryName.NETWORK_ACTIVITY,
        class_name=ClassName.NETWORK_FLOW,
        alert_type="T",
        severity=Severity.INFO,
        raw_event={}
    )
    
    # 1. 10.0.4.15 (Private)
    alert1 = base_alert.model_copy()
    alert1.src_ip = "10.0.4.15"
    
    # 2. 172.16.0.1 (Private - Start of 172.16.0.0/12 block)
    alert2 = base_alert.model_copy()
    alert2.src_ip = "172.16.0.1"
    
    # 3. 172.31.255.255 (Private - End of 172.16.0.0/12 block)
    alert3 = base_alert.model_copy()
    alert3.src_ip = "172.31.255.255"
    
    # 4. 172.32.0.1 (Public - Outside private block)
    alert4 = base_alert.model_copy()
    alert4.src_ip = "172.32.0.1"
    
    package, _, _ = gateway.process([alert1, alert2, alert3, alert4], PrivacyPolicy.strict_external())
    
    # 10.0.4.15 should be tokenized
    assert "PRIVATE_IP_" in package.evidence_items[0].src_ip
    assert package.evidence_items[0].src_ip != "10.0.4.15"
    
    # 172.16.0.1 should be tokenized
    assert "PRIVATE_IP_" in package.evidence_items[1].src_ip
    assert package.evidence_items[1].src_ip != "172.16.0.1"
    
    # 172.31.255.255 should be tokenized
    assert "PRIVATE_IP_" in package.evidence_items[2].src_ip
    assert package.evidence_items[2].src_ip != "172.31.255.255"
    
    # 172.32.0.1 should NOT be tokenized (it is public)
    assert package.evidence_items[3].src_ip == "172.32.0.1"
