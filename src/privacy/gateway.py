import copy
import ipaddress
from typing import List, Tuple, Optional
from src.models.schema import NormalizedAlert
from src.models.privacy import PrivacyClass, PrivacyAction
from src.models.safe_evidence import (
    SafeEvidenceItem,
    SafeEvidencePackage,
    PackagePrivacyContext,
    TransformationAudit,
    TransformationRecord
)
from src.privacy.policy import PrivacyPolicy
from src.privacy.tokenization import AliasService
from src.privacy.redactor import SecretRedactor
from src.privacy.inspector import FreeTextInspector

class PrivacyGatewayError(Exception):
    """Raised when PrivacyGateway fails to safely process evidence (Fail-Closed)."""
    pass

class LocalPrivacyGateway:
    """
    Local Privacy Gateway enforcing model trust boundary rules.
    Converts NormalizedAlert objects into AI-safe SafeEvidencePackage payloads.
    Makes ZERO network calls, preserves raw evidence locally, and fails closed on error.
    """
    def __init__(self, redactor: Optional[SecretRedactor] = None):
        self.redactor = redactor or SecretRedactor()

    def process(
        self,
        alerts: List[NormalizedAlert],
        policy: Optional[PrivacyPolicy] = None
    ) -> Tuple[SafeEvidencePackage, PackagePrivacyContext, TransformationAudit]:
        if not alerts:
            raise PrivacyGatewayError("Cannot process empty alert list.")
            
        policy = policy or PrivacyPolicy.strict_external()
        
        # Enforce tenant isolation consistency within batch
        tenant_id = alerts[0].tenant_id
        for alert in alerts:
            if alert.tenant_id != tenant_id:
                raise PrivacyGatewayError("Multi-tenant mixing detected in single gateway process batch.")
                
        alias_service = AliasService()
        inspector = FreeTextInspector(self.redactor, alias_service)
        
        package = SafeEvidencePackage(policy_profile=policy.name)
        privacy_context = PackagePrivacyContext(
            package_id=package.package_id,
            tenant_id=tenant_id
        )
        audit = TransformationAudit(
            package_id=package.package_id,
            tenant_id=tenant_id
        )
        
        try:
            for idx, alert in enumerate(alerts, start=1):
                # Ensure no mutation of input alert
                alert_copy = alert.model_copy(deep=True)
                evidence_ref = f"EVIDENCE_{idx:03d}"
                
                # Record local reference mapping
                privacy_context.evidence_reference_map[evidence_ref] = {
                    "internal_alert_id": alert_copy.id,
                    "source_event_id": alert_copy.source_event_id
                }
                
                # Sanitize User
                user_alias = None
                if alert_copy.user:
                    user_alias = alias_service.get_or_create_alias(alert_copy.user, "USER")
                    audit.records.append(TransformationRecord(
                        alert_id=alert_copy.id,
                        field_name="user",
                        privacy_class=PrivacyClass.DIRECT_IDENTIFIER,
                        action_taken=PrivacyAction.TOKENIZE,
                        output_marker=user_alias,
                        reason="Tokenized user identity for model safety"
                    ))
                    
                # Sanitize Host
                host_alias = None
                if alert_copy.host:
                    host_alias = alias_service.get_or_create_alias(alert_copy.host, "HOST")
                    audit.records.append(TransformationRecord(
                        alert_id=alert_copy.id,
                        field_name="host",
                        privacy_class=PrivacyClass.INTERNAL_ASSET_IDENTIFIER,
                        action_taken=PrivacyAction.TOKENIZE,
                        output_marker=host_alias,
                        reason="Tokenized internal host for model safety"
                    ))
                    
                # Sanitize Src IP
                src_ip_alias = None
                if alert_copy.src_ip:
                    try:
                        ip_obj = ipaddress.ip_address(alert_copy.src_ip)
                        if ip_obj.is_private:
                            src_ip_alias = alias_service.get_or_create_alias(alert_copy.src_ip, "PRIVATE_IP")
                            audit.records.append(TransformationRecord(
                                alert_id=alert_copy.id,
                                field_name="src_ip",
                                privacy_class=PrivacyClass.INTERNAL_ASSET_IDENTIFIER,
                                action_taken=PrivacyAction.TOKENIZE,
                                output_marker=src_ip_alias,
                                reason="Tokenized private source IP"
                            ))
                        else:
                            src_ip_alias = alert_copy.src_ip
                    except ValueError:
                        # Fallback if invalid IP string (treat as public/unknown)
                        src_ip_alias = alert_copy.src_ip
                        
                # Sanitize Dst IP
                dst_ip_alias = None
                if alert_copy.dst_ip:
                    try:
                        ip_obj = ipaddress.ip_address(alert_copy.dst_ip)
                        if ip_obj.is_private:
                            dst_ip_alias = alias_service.get_or_create_alias(alert_copy.dst_ip, "PRIVATE_IP")
                        else:
                            dst_ip_alias = alert_copy.dst_ip
                    except ValueError:
                        dst_ip_alias = alert_copy.dst_ip

                # Sanitize Free-Text Command Line
                sanitized_cmdline = None
                if alert_copy.command_line:
                    cmd_text, is_safe = inspector.inspect_and_sanitize(alert_copy.command_line)
                    sanitized_cmdline = cmd_text if is_safe else "<WITHHELD_UNSAFE_TEXT>"
                    audit.records.append(TransformationRecord(
                        alert_id=alert_copy.id,
                        field_name="command_line",
                        privacy_class=PrivacyClass.UNCLASSIFIED_FREE_TEXT,
                        action_taken=PrivacyAction.LOCAL_ONLY if not is_safe else PrivacyAction.REDACT,
                        output_marker=sanitized_cmdline,
                        reason="Inspected and sanitized command line free text"
                    ))

                # Sanitize Free-Text Message
                sanitized_msg = None
                if alert_copy.message:
                    msg_text, is_safe = inspector.inspect_and_sanitize(alert_copy.message)
                    sanitized_msg = msg_text if is_safe else "<WITHHELD_UNSAFE_TEXT>"

                # Construct AI-Safe Item (omitting tenant_id, raw source_event_id, internal alert ID, and raw_event)
                safe_item = SafeEvidenceItem(
                    evidence_ref=evidence_ref,
                    timestamp=alert_copy.timestamp,
                    source_type=alert_copy.source_type,
                    category_name=alert_copy.category_name,
                    class_name=alert_copy.class_name,
                    alert_type=alert_copy.alert_type,
                    severity=alert_copy.severity,
                    user=user_alias,
                    host=host_alias,
                    src_ip=src_ip_alias,
                    dst_ip=dst_ip_alias,
                    domain=alert_copy.domain,
                    process_name=alert_copy.process_name,
                    command_line=sanitized_cmdline,
                    file_path=alert_copy.file_path,
                    file_hash=alert_copy.file_hash,
                    file_hash_algorithm=alert_copy.file_hash_algorithm,
                    message=sanitized_msg,
                    schema_version=alert_copy.schema_version
                )
                package.evidence_items.append(safe_item)

            privacy_context.entity_alias_map = alias_service.get_alias_map()
            return package, privacy_context, audit

        except Exception as e:
            # FAIL-CLOSED GUARANTEE: Never emit partially sanitized payload
            raise PrivacyGatewayError(f"Privacy Gateway failed during execution: {str(e)}") from e
