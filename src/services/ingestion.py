import uuid
import traceback
import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select

from src.db.models import RawEventModel, NormalizedAlertModel, ProcessingStatus
from src.models.schema import NormalizedAlert

try:
    from src.normalizers.mock_xdr import MockXDRNormalizer
    from src.normalizers.mock_iam import MockIAMNormalizer
    from src.normalizers.mock_firewall import MockFirewallNormalizer
    from src.normalizers.canonical import GenericCanonicalNormalizer
    has_normalizers = True
except ImportError:
    has_normalizers = False

class SourceNormalizerRouter:
    """Routes an incoming event to the appropriate normalizer based on source_type."""
    def __init__(self):
        self.normalizers = {}
        if has_normalizers:
            self.normalizers["XDR"] = MockXDRNormalizer()
            self.normalizers["IAM"] = MockIAMNormalizer()
            self.normalizers["FIREWALL"] = MockFirewallNormalizer()
            self.normalizers["FW"] = MockFirewallNormalizer()
            self.normalizers["SENTINELOPS_CANONICAL"] = GenericCanonicalNormalizer()

    def normalize(self, source_type: str, raw_payload: Dict[str, Any], tenant_id: str) -> NormalizedAlert:
        normalizer = self.normalizers.get(source_type.upper())
        if not normalizer:
            raise ValueError(f"No normalizer found for source_type: {source_type}")
        return normalizer.normalize(raw_payload, tenant_id=tenant_id)


def sanitize_validation_error(e: Exception) -> str:
    """Extracts safe error info without raw values or stack traces."""
    if hasattr(e, "errors") and callable(e.errors):
        # Pydantic validation error
        errs = e.errors()
        safe_messages = []
        for err in errs:
            loc = ".".join(str(l) for l in err.get("loc", []))
            msg = err.get("msg", "Validation error")
            safe_messages.append(f"field='{loc}' reason='{msg}'")
        return " | ".join(safe_messages)
    traceback.print_exc()
    return f"error_code=UNKNOWN_NORMALIZATION_FAILURE reason='Unclassified error during normalization: {str(e)}'"


class IngestionService:
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.router = SourceNormalizerRouter()

    async def ingest_event(
        self,
        tenant_id: str,
        source_type: str,
        source_vendor: str,
        source_product: str,
        payload: Dict[str, Any]
    ) -> tuple[str, Optional[str], Optional[str]]:
        
        # Compute deterministic hash of payload
        payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        # TRANSACTION A: Commit Raw Evidence First
        raw_event = RawEventModel(
            tenant_id=tenant_id,
            source_type=source_type,
            source_vendor=source_vendor,
            source_product=source_product,
            source_event_id=payload.get("vendor_id"),
            received_at=datetime.now(timezone.utc),
            raw_payload=payload,
            raw_payload_sha256=payload_hash,
            processing_status=ProcessingStatus.RECEIVED
        )
        
        self.db.add(raw_event)
        try:
            await self.db.commit()
        except SQLAlchemyError as e:
            await self.db.rollback()
            raise Exception("DATABASE_ERROR") from e

        raw_id = raw_event.id

        # ATTEMPT NORMALIZATION IN MEMORY
        try:
            normalized = self.router.normalize(source_type, payload, tenant_id)
        except Exception as e:
            # NORMALIZATION FAILURE
            error_msg = sanitize_validation_error(e)
            
            # TRANSACTION B (Failure path 1)
            raw_event.processing_status = ProcessingStatus.NORMALIZATION_FAILED
            raw_event.normalization_error = error_msg
            self.db.add(raw_event)
            await self.db.commit()
            return "NORMALIZATION_FAILED", str(raw_id), error_msg

        # TRANSACTION B (Success or Persistence Failure)
        norm_model = NormalizedAlertModel(
            raw_event_id=raw_id,
            tenant_id=normalized.tenant_id,
            source_event_id=normalized.source_event_id,
            timestamp=normalized.timestamp,
            ingested_at=normalized.ingested_at,
            source_type=normalized.source_type.value,
            source_vendor=normalized.source_vendor,
            source_product=normalized.source_product,
            category_name=normalized.category_name.value,
            class_name=normalized.class_name.value,
            alert_type=normalized.alert_type,
            severity=normalized.severity.value,
            user=normalized.user,
            host=normalized.host,
            src_ip=normalized.src_ip,
            dst_ip=normalized.dst_ip,
            domain=normalized.domain,
            process_name=normalized.process_name,
            command_line=normalized.command_line,
            file_path=normalized.file_path,
            file_hash=normalized.file_hash,
            file_hash_algorithm=normalized.file_hash_algorithm.value if normalized.file_hash_algorithm else None,
            message=normalized.message,
            schema_version=normalized.schema_version
        )
        self.db.add(norm_model)
        raw_event.processing_status = ProcessingStatus.NORMALIZED
        self.db.add(raw_event)
        
        try:
            await self.db.commit()
            return "NORMALIZED", str(raw_id), str(norm_model.id)
        except SQLAlchemyError as e:
            # PERSISTENCE FAILURE
            await self.db.rollback()
            # Fetch the raw event again since we rolled back
            res = await self.db.execute(select(RawEventModel).where(RawEventModel.id == raw_id))
            raw_to_update = res.scalar_one()
            raw_to_update.processing_status = ProcessingStatus.PERSISTENCE_FAILED
            raw_to_update.normalization_error = "error_code=PERSISTENCE_FAILURE reason='Failed to save normalized alert to database'"
            self.db.add(raw_to_update)
            await self.db.commit()
            
            return "PERSISTENCE_FAILED", str(raw_id), "error_code=PERSISTENCE_FAILURE"
