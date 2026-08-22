import pytest
import pytest_asyncio
import json
import hashlib
from typing import Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from src.db.models import Base, RawEventModel, NormalizedAlertModel, StorageTier, ProcessingStatus
from src.services.ingestion import IngestionService

pytestmark = pytest.mark.asyncio

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session

async def test_storage_tier_defaults_and_hash(db_session: AsyncSession):
    service = IngestionService(db_session)
    
    payload = {
        "vendor": "AcmeCorp",
        "product": "Firewall",
        "action": "block",
        "src_ip": "1.2.3.4",
        "timestamp": "2023-01-01T12:00:00Z"
    }
    
    # Expected hash
    payload_bytes = json.dumps(payload, sort_keys=True).encode('utf-8')
    expected_hash = hashlib.sha256(payload_bytes).hexdigest()
    
    # Ingest (will fail normalization because 'action' doesn't map to a valid schema without 'vendor_id', etc)
    # Actually, MockFirewallNormalizer expects 'src_ip', 'action', etc. Let's use a payload that succeeds.
    success_payload = {
        "fw_rule_id": "FW-999",
        "action": "DENY",
        "src": "10.0.0.5",
        "dst": "192.168.1.10",
        "timestamp": "2024-01-01T00:00:00Z"
    }
    success_bytes = json.dumps(success_payload, sort_keys=True).encode('utf-8')
    success_hash = hashlib.sha256(success_bytes).hexdigest()
    
    status, raw_id, norm_id = await service.ingest_event(
        tenant_id="tenant-123",
        source_type="FIREWALL",
        source_vendor="AcmeCorp",
        source_product="Firewall",
        payload=success_payload
    )
    
    assert status == "NORMALIZED"
    
    import uuid
    # Verify RawEvent
    result = await db_session.execute(select(RawEventModel).where(RawEventModel.id == uuid.UUID(raw_id)))
    raw_event = result.scalar_one()
    
    assert raw_event.storage_tier == StorageTier.HOT_POSTGRES
    assert raw_event.external_storage_pointer is None
    assert raw_event.raw_payload_sha256 == success_hash
    assert raw_event.processing_status == ProcessingStatus.NORMALIZED
    
    # Verify NormalizedAlert links back securely
    result_norm = await db_session.execute(select(NormalizedAlertModel).where(NormalizedAlertModel.id == uuid.UUID(norm_id)))
    norm_alert = result_norm.scalar_one()
    
    assert norm_alert.raw_event_id == raw_event.id
    
    # Verify failure retains raw evidence
    fail_payload = {"bad": "data"}
    fail_bytes = json.dumps(fail_payload, sort_keys=True).encode('utf-8')
    fail_hash = hashlib.sha256(fail_bytes).hexdigest()
    
    status_fail, raw_fail_id, error_msg = await service.ingest_event(
        tenant_id="tenant-123",
        source_type="FIREWALL",
        source_vendor="AcmeCorp",
        source_product="Firewall",
        payload=fail_payload
    )
    
    assert status_fail == "NORMALIZATION_FAILED"
    
    result_fail = await db_session.execute(select(RawEventModel).where(RawEventModel.id == uuid.UUID(raw_fail_id)))
    raw_fail_event = result_fail.scalar_one()
    
    assert raw_fail_event.storage_tier == StorageTier.HOT_POSTGRES
    assert raw_fail_event.external_storage_pointer is None
    assert raw_fail_event.raw_payload_sha256 == fail_hash
    assert raw_fail_event.processing_status == ProcessingStatus.NORMALIZATION_FAILED

def test_hash_stability():
    # Proof that the hash is deterministic and stable
    payload = {"b": 2, "a": 1, "c": [3, 2, 1]}
    
    bytes_1 = json.dumps(payload, sort_keys=True).encode('utf-8')
    hash_1 = hashlib.sha256(bytes_1).hexdigest()
    
    payload_reordered = {"c": [3, 2, 1], "a": 1, "b": 2}
    bytes_2 = json.dumps(payload_reordered, sort_keys=True).encode('utf-8')
    hash_2 = hashlib.sha256(bytes_2).hexdigest()
    
    assert hash_1 == hash_2
