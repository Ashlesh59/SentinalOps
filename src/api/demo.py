import os
import uuid
import traceback
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from src.db.database import get_db
from src.services.ingestion import IngestionService
from src.services.pipeline_tracker import pipeline_tracker
from src.brain1.engine import run_correlation
from src.db.models import IncidentModel, InvestigationJobModel, JobStatus
from src.brain2.worker import Brain2Worker
from src.brain2.provider import get_provider
from src.brain1.snapshot import SnapshotBuilder
from src.brain2.selector import EvidenceSelector

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])

ENABLE_DEMO_SCENARIOS = os.environ.get("ENABLE_DEMO_SCENARIOS", "true").lower() == "true"
DEMO_TENANT_ID = "tenant-test"

async def run_demo_attack_chain(session: AsyncSession):
    try:
        # Start live pipeline tracking
        pipeline_tracker.start_pipeline("DEMO_ATTACK_CHAIN")
        
        # 1. Ingest Raw Telemetry
        ingestion_service = IngestionService(session)
        
        # Advance to Normalizing Evidence
        pipeline_tracker.advance_stage("RECEIVING_TELEMETRY", "NORMALIZING_EVIDENCE")
        
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

        # 3. Exact Duplicate Deliveries
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

        # 4. XDR Events - 5 Credential Access alerts
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

        # 3. Brain 1 Heuristic Correlation
        pipeline_tracker.advance_stage("NORMALIZING_EVIDENCE", "BRAIN1_CORRELATION")
        await run_correlation(session, DEMO_TENANT_ID)

        # Find the newly generated or latest incident
        inc = (await session.execute(
            select(IncidentModel)
            .where(IncidentModel.tenant_id == DEMO_TENANT_ID)
            .order_by(desc(IncidentModel.last_seen))
        )).scalars().first()

        # 4. Privacy Preparation
        pipeline_tracker.advance_stage("BRAIN1_CORRELATION", "PRIVACY_PREPARATION")
        if inc:
            builder = SnapshotBuilder(session, DEMO_TENANT_ID)
            snapshot = await builder.build_snapshot(inc.id)
            selector = EvidenceSelector()
            safe_package = await selector.extract_package(snapshot)
            fingerprint = safe_package.package_fingerprint
            
            # 5. Brain 2 AI Investigation
            pipeline_tracker.advance_stage("PRIVACY_PREPARATION", "BRAIN2_INVESTIGATION")
            
            # Create and execute investigation job
            job = InvestigationJobModel(
                tenant_id=DEMO_TENANT_ID,
                incident_id=inc.id,
                incident_version=inc.version,
                safe_package_fingerprint=fingerprint,
                status=JobStatus.PENDING
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            
            worker = Brain2Worker(session=session, provider=get_provider())
            await worker.execute_job(job)

        # 6. Complete
        pipeline_tracker.complete_pipeline({
            "raw_events": 22,
            "analytical_signals": 4,
            "correlated_incidents": 1
        })
    except Exception as e:
        traceback.print_exc()
        pipeline_tracker.fail_pipeline(str(e))
        raise

@router.post("/scenarios/attack-chain", status_code=202)
async def trigger_demo_scenario(session: AsyncSession = Depends(get_db)):
    if not ENABLE_DEMO_SCENARIOS:
        raise HTTPException(status_code=403, detail="Demo scenarios are disabled.")
    
    await run_demo_attack_chain(session)
    return {"status": "success", "message": "Demo scenario processed through full pipeline."}
