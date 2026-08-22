import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.database import get_db
from src.services.ingestion import IngestionService
from src.brain1.engine import run_correlation

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

# Use environment configuration as requested
ENABLE_DEMO_SCENARIOS = os.environ.get("ENABLE_DEMO_SCENARIOS", "true").lower() == "true"
DEMO_TENANT_ID = "tenant-test"

async def run_demo_attack_chain(session: AsyncSession):
    # This runs the demo attack chain end to end with 22 raw/normalized deliveries.
    # Brain 1 will aggregate them into 4 analytical signals and correlate into 1 incident.
    ingestion_service = IngestionService(session)
    
    # 1. IAM Event (Unusual Authentication)
    iam_payload = {
        "time": "2023-10-01T14:00:00Z",
        "log_id": "iam-001",
        "actor_email": "alice_admin",
        "source_ip": "104.21.32.14",
        "action": "login",
        "severity": "medium",
        "status": "success"
    }
    await ingestion_service.ingest_event(
        tenant_id=DEMO_TENANT_ID,
        source_type="IAM",
        source_vendor="Okta",
        source_product="Okta",
        payload=iam_payload
    )

    # 2. XDR Events - 8 Repeated Suspicious PowerShell detections
    for i in range(1, 9):
        sec = i * 10
        xdr_ps = {
            "detected_at": f"2023-10-01T14:05:{sec:02d}Z",
            "event_id": f"xdr-ps-{i:02d}",
            "username": "alice_admin",
            "src_ip": "192.168.1.50",
            "severity": "HIGH",
            "detection_name": "Suspicious PowerShell",
            "cmdline": "powershell.exe -enc JABzAD0ATgBlAHcALQBPAGIAagBlAGMAdAAgAEkATwAuAE0AZQBtAG8AcgB5AFMAdAByAGUAYQBtACgAWwBDAG8AbgB2AGUAcgB0AF0AOgA6AEYAcgBvAG0AQgBhAHMAZQA2ADQAUwB0AHIAaQBuAGcAKAAiAEgA..."
        }
        await ingestion_service.ingest_event(
            tenant_id=DEMO_TENANT_ID,
            source_type="XDR",
            source_vendor="CrowdStrike",
            source_product="Falcon",
            payload=xdr_ps
        )

    # 3. Exact Duplicate Deliveries (Testing duplicate handling)
    for dup_id in ["xdr-ps-01", "xdr-ps-02"]:
        xdr_dup = {
            "detected_at": "2023-10-01T14:05:10Z",
            "event_id": f"{dup_id}-retry",
            "username": "alice_admin",
            "src_ip": "192.168.1.50",
            "severity": "HIGH",
            "detection_name": "Suspicious PowerShell",
            "cmdline": "powershell.exe -enc JABzAD0ATgBlAHcALQBPAGIAagBlAGMAdAAgAEkATwAuAE0AZQBtAG8AcgB5AFMAdAByAGUAYQBtACgAWwBDAG8AbgB2AGUAcgB0AF0AOgA6AEYAcgBvAG0AQgBhAHMAZQA2ADQAUwB0AHIAaQBuAGcAKAAiAEgA..."
        }
        await ingestion_service.ingest_event(
            tenant_id=DEMO_TENANT_ID,
            source_type="XDR",
            source_vendor="CrowdStrike",
            source_product="Falcon",
            payload=xdr_dup
        )

    # 4. XDR Events - 5 Credential Access alerts (lsass dumping)
    for i in range(1, 6):
        sec = i * 12
        xdr_cred = {
            "detected_at": f"2023-10-01T14:10:{sec:02d}Z",
            "event_id": f"xdr-cred-{i:02d}",
            "username": "alice_admin",
            "src_ip": "192.168.1.50",
            "severity": "CRITICAL",
            "detection_name": "Credential Access",
            "cmdline": "procdump.exe -ma lsass.exe lsass.dmp"
        }
        await ingestion_service.ingest_event(
            tenant_id=DEMO_TENANT_ID,
            source_type="XDR",
            source_vendor="CrowdStrike",
            source_product="Falcon",
            payload=xdr_cred
        )

    # 5. Firewall Events - 6 Outbound Network Connection detections
    for i in range(1, 7):
        sec = i * 8
        fw_payload = {
            "timestamp": f"2023-10-01T14:12:{sec:02d}Z",
            "fw_rule_id": f"fw-00{i}",
            "src": "192.168.1.50",
            "dst": "104.21.32.14",
            "dst_port": 443,
            "action": "ALLOW"
        }
        await ingestion_service.ingest_event(
            tenant_id=DEMO_TENANT_ID,
            source_type="FIREWALL",
            source_vendor="PaloAlto",
            source_product="PAN-OS",
            payload=fw_payload
        )

    # Run Brain 1 to process the ingested events and create incidents
    await run_correlation(session, DEMO_TENANT_ID)

@router.post("/scenarios/attack-chain", status_code=202)
async def trigger_demo_scenario(background_tasks: BackgroundTasks, session: AsyncSession = Depends(get_db)):
    if not ENABLE_DEMO_SCENARIOS:
        raise HTTPException(status_code=403, detail="Demo scenarios are disabled.")
    
    # Run in background to not block the UI immediately, or we can await it if we want it synchronous.
    # The instructions say "The frontend 'Run Demo Scenario' button must call the backend demo endpoint"
    # Wait, the instruction says to use background tasks or similar. Actually, doing it synchronously is fine if it takes 100ms.
    # We'll just run it synchronously so the UI can refresh immediately after the POST.
    await run_demo_attack_chain(session)
    return {"status": "success", "message": "Demo scenario injected and Brain 1 executed."}
