import pytest
import json
import os
import httpx
from src.main import app

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "ground_truth_p4.json")

def load_ground_truth():
    with open(FIXTURE_PATH, "r") as f:
        return json.load(f)

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import engine
from src.db.models import Base

@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database():
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())
    yield
    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(table.delete())

@pytest.fixture(scope="session")
def ground_truth():
    return load_ground_truth()

@pytest_asyncio.fixture
async def async_client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=("127.0.0.1", 123), raise_app_exceptions=True), base_url="http://test") as client:
        yield client

async def run_scenario(client, scenario_name: str, ground_truth: dict):
    scenario = ground_truth["scenarios"][scenario_name]
    tenant_id = f"tenant_{scenario_name.lower()}"
    
    # 1. Ingest events
    for event in scenario["events"]:
        payload = event["payload"]
        st = event["source_type"]
        if st == "xdr":
            payload["event_id"] = event["source_event_id"]
            payload["detected_at"] = payload.get("timestamp") or event["received_at"]
            if "process" in payload: payload["process_name"] = payload["process"]
            if "user" in payload: payload["username"] = payload["user"]
            if "host" in payload: payload["hostname"] = payload["host"]
            if "event" in payload: payload["detection_name"] = payload["event"]
            if "file_hash" in payload: payload["sha256"] = payload["file_hash"]
        elif st == "iam":
            payload["log_id"] = event["source_event_id"]
            payload["time"] = payload.get("timestamp") or event["received_at"]
            if "user" in payload: payload["actor_email"] = payload["user"]
            if "src_ip" in payload: payload["source_ip"] = payload["src_ip"]
            
            # Map severity to IAM outcome
            sev = payload.get("severity", "info").lower()
            if sev == "info": payload["outcome"] = "success"
            elif sev == "low": payload["outcome"] = "failure"
            else: payload["outcome"] = "suspicious"
            
        elif st == "fw":
            payload["fw_rule_id"] = event["source_event_id"]
            payload["timestamp"] = payload.get("timestamp") or event["received_at"]
            if "src_ip" in payload: payload["src"] = payload["src_ip"]
            if "dst_ip" in payload: payload["dst"] = payload["dst_ip"]
            if "domain" in payload: payload["dns_query"] = payload["domain"]
            
            # Map severity to FW action
            sev = payload.get("severity", "info").lower()
            if sev in ["low", "medium", "high", "critical"]:
                payload["action"] = "DENY"
            else:
                payload["action"] = "ALLOW"
        
        resp = await client.post("/api/v1/events", json={
            "tenant_id": tenant_id,
            "source_type": st,
            "source_vendor": event["source_vendor"],
            "source_product": event["source_product"],
            "payload": payload
        })
        assert resp.status_code == 201, f"Failed to ingest event: {resp.text}"

    # 2. Run correlation manually (Phase 4 MVP design)
    corr_resp = await client.post("/api/v1/correlation/run", json={"tenant_id": tenant_id})
    assert corr_resp.status_code == 200

    # 3. Retrieve incidents
    inc_resp = await client.get(f"/api/v1/incidents?tenant_id={tenant_id}")
    assert inc_resp.status_code == 200
    incidents = inc_resp.json()

    # 4. Assert against expectations
    expected_incidents = scenario.get("expected_incidents", 0)
    
    # Count should match
    assert len(incidents) == expected_incidents, f"Scenario {scenario_name} failed incident count, expected {expected_incidents} got {len(incidents)}"
    
    return incidents


@pytest.mark.asyncio
async def test_scenario_a_real_attack(async_client, ground_truth):
    incidents = await run_scenario(async_client, "A", ground_truth)
    if incidents:
        assert incidents[0]["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_scenario_b_exact_duplicate(async_client, ground_truth):
    incidents = await run_scenario(async_client, "B", ground_truth)


@pytest.mark.asyncio
async def test_scenario_c_repeated_burst(async_client, ground_truth):
    incidents = await run_scenario(async_client, "C", ground_truth)


@pytest.mark.asyncio
async def test_scenario_d_unrelated(async_client, ground_truth):
    incidents = await run_scenario(async_client, "D", ground_truth)


@pytest.mark.asyncio
async def test_scenario_e_benign_admin(async_client, ground_truth):
    incidents = await run_scenario(async_client, "E", ground_truth)
    if incidents:
        assert incidents[0]["severity"] == "low"


@pytest.mark.asyncio
async def test_scenario_f_cross_tenant_trap(async_client, ground_truth):
    # Ingesting for F will be split by the run_scenario wrapper, 
    # but the fixture actually has events for different tenants.
    # We need a custom runner for F to handle multiple tenants.
    scenario = ground_truth["scenarios"]["F"]
    
    for event in scenario["events"]:
        payload = event["payload"]
        st = event["source_type"]
        if st == "xdr":
            payload["event_id"] = event["source_event_id"]
            payload["detected_at"] = payload.get("timestamp") or event["received_at"]
            if "process" in payload: payload["process_name"] = payload["process"]
            if "user" in payload: payload["username"] = payload["user"]
            if "host" in payload: payload["hostname"] = payload["host"]
            if "event" in payload: payload["detection_name"] = payload["event"]
            if "file_hash" in payload: payload["sha256"] = payload["file_hash"]
        elif st == "iam":
            payload["log_id"] = event["source_event_id"]
            payload["time"] = payload.get("timestamp") or event["received_at"]
            if "user" in payload: payload["actor_email"] = payload["user"]
            if "src_ip" in payload: payload["source_ip"] = payload["src_ip"]
            sev = payload.get("severity", "info").lower()
            if sev == "info": payload["outcome"] = "success"
            elif sev == "low": payload["outcome"] = "failure"
            else: payload["outcome"] = "suspicious"
        elif st == "fw":
            payload["fw_rule_id"] = event["source_event_id"]
            payload["timestamp"] = payload.get("timestamp") or event["received_at"]
            if "src_ip" in payload: payload["src"] = payload["src_ip"]
            if "dst_ip" in payload: payload["dst"] = payload["dst_ip"]
            if "domain" in payload: payload["dns_query"] = payload["domain"]
            sev = payload.get("severity", "info").lower()
            if sev in ["low", "medium", "high", "critical"]:
                payload["action"] = "DENY"
            else:
                payload["action"] = "ALLOW"
        
        resp = await async_client.post("/api/v1/events", json={
            "tenant_id": event["tenant_id"],
            "source_type": st,
            "source_vendor": event["source_vendor"],
            "source_product": event["source_product"],
            "payload": payload
        })
        assert resp.status_code == 201, f"Failed to ingest event: {resp.text}"

    # Run for both tenants
    await async_client.post("/api/v1/correlation/run", json={"tenant_id": "tenant_1"})
    await async_client.post("/api/v1/correlation/run", json={"tenant_id": "tenant_2"})

    inc1 = (await async_client.get("/api/v1/incidents?tenant_id=tenant_1")).json()
    inc2 = (await async_client.get("/api/v1/incidents?tenant_id=tenant_2")).json()

    # The run_scenario already asserts inside, but we manually assert F because it's cross-tenant
    expected = scenario.get("expected_incidents", 0)
    assert len(inc1) == expected
    assert len(inc2) == expected


@pytest.mark.asyncio
async def test_scenario_g_shared_ip_trap(async_client, ground_truth):
    incidents = await run_scenario(async_client, "G", ground_truth)


@pytest.mark.asyncio
async def test_scenario_h_late_arrival(async_client, ground_truth):
    incidents = await run_scenario(async_client, "H", ground_truth)
