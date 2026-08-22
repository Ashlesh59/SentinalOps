import uuid
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.database import get_db
from src.db.models import NormalizedAlertModel
from src.services.ingestion import IngestionService
from src.models.schema import NormalizedAlert
from src.privacy.gateway import LocalPrivacyGateway
from src.privacy.policy import PrivacyPolicy
from src.ingestion.file_service import FileImportService
from src.db.models import ImportJobModel
from sqlalchemy import select
import uuid

router = APIRouter()

class IngestionEnvelope(BaseModel):
    tenant_id: str
    source_type: str
    source_vendor: str
    source_product: str
    payload: Dict[str, Any]

class IngestionSuccessResponse(BaseModel):
    status: str
    normalized_alert_id: str
    raw_event_id: str

class IngestionFailureResponse(BaseModel):
    status: str
    raw_event_id: str
    error: str

class SafeEvidenceRequest(BaseModel):
    tenant_id: str
    alert_ids: List[str]

@router.post("/events", status_code=status.HTTP_201_CREATED, responses={422: {"model": IngestionFailureResponse}})
async def ingest_event(envelope: IngestionEnvelope, db: AsyncSession = Depends(get_db)):
    service = IngestionService(db)
    try:
        proc_status, raw_id, norm_id_or_error = await service.ingest_event(
            tenant_id=envelope.tenant_id,
            source_type=envelope.source_type,
            source_vendor=envelope.source_vendor,
            source_product=envelope.source_product,
            payload=envelope.payload
        )
    except Exception as e:
        if str(e) == "DATABASE_ERROR":
            raise HTTPException(status_code=500, detail="DATABASE_ERROR")
        raise HTTPException(status_code=500, detail=str(e))

    if proc_status == "NORMALIZED":
        return IngestionSuccessResponse(
            status=proc_status,
            normalized_alert_id=norm_id_or_error,
            raw_event_id=raw_id
        )
    else:
        # FastAPI allows returning a custom Response or raising HTTPException.
        # But we want to return JSON with 422.
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=IngestionFailureResponse(
                status=proc_status,
                raw_event_id=raw_id,
                error=norm_id_or_error
            ).model_dump()
        )

@router.post("/events/batch", status_code=status.HTTP_207_MULTI_STATUS)
async def ingest_batch(envelopes: List[IngestionEnvelope], db: AsyncSession = Depends(get_db)):
    if len(envelopes) > 1000:
        raise HTTPException(status_code=400, detail="Batch size limit exceeded (max 1000)")
        
    service = IngestionService(db)
    results = []
    
    # Process sequentially for safety, though async gather could be faster
    for envelope in envelopes:
        try:
            proc_status, raw_id, norm_id_or_error = await service.ingest_event(
                tenant_id=envelope.tenant_id,
                source_type=envelope.source_type,
                source_vendor=envelope.source_vendor,
                source_product=envelope.source_product,
                payload=envelope.payload
            )
            if proc_status == "NORMALIZED":
                results.append({"status": proc_status, "raw_event_id": raw_id, "normalized_alert_id": norm_id_or_error})
            else:
                results.append({"status": proc_status, "raw_event_id": raw_id, "error": norm_id_or_error})
        except Exception as e:
            results.append({"status": "FAILED", "error": str(e)})
            
    return {"results": results}

@router.post("/webhooks/{integration_id}", status_code=status.HTTP_201_CREATED)
async def ingest_webhook(integration_id: str, payload: Dict[str, Any], tenant_id: str = "default-tenant", db: AsyncSession = Depends(get_db)):
    # Simple webhook ingestion that passes the generic payload
    service = IngestionService(db)
    try:
        proc_status, raw_id, norm_id_or_error = await service.ingest_event(
            tenant_id=tenant_id,
            source_type=payload.get("source_type", "UNKNOWN"),
            source_vendor=payload.get("vendor", "UnknownWebhookVendor"),
            source_product=payload.get("product", "UnknownWebhookProduct"),
            payload=payload
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    return {"status": proc_status, "raw_event_id": raw_id, "result": norm_id_or_error}

@router.post("/imports", status_code=status.HTTP_202_ACCEPTED)
async def create_import(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    tenant_id: str = Form("default-tenant"),
    source_hint: str = Form(None),
    db: AsyncSession = Depends(get_db)
):
    # Verify file extension
    ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    if ext not in ['csv', 'json', 'jsonl', 'ndjson']:
        raise HTTPException(status_code=400, detail="Unsupported file extension")
        
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:  # 50MB limit for hackathon
        raise HTTPException(status_code=400, detail="File size exceeds limit")
        
    svc = FileImportService(db)
    job_id = await svc.create_import_job(tenant_id, file.filename)
    
    # Background task requires its own session generally in FastAPI/SQLAlchemy unless session is kept open.
    # We will pass the bytes directly. 
    # WARNING: Using Depends(get_db) session in background task can cause DetachedInstanceError or similar if the session closes.
    # For the hackathon, we'll quickly open a new session in the background wrapper.
    async def process_in_background(job_id: str, tenant_id: str, content: bytes, filename: str, source_hint: str):
        from src.db.database import async_session
        async with async_session() as bg_db:
            bg_svc = FileImportService(bg_db)
            await bg_svc.process_file(job_id, tenant_id, content, filename, source_hint)
            
    background_tasks.add_task(process_in_background, job_id, tenant_id, content, file.filename, source_hint)
    
    return {"import_id": job_id, "status": "PENDING"}

@router.get("/imports/{import_id}")
async def get_import_status(import_id: str, tenant_id: str = "default-tenant", db: AsyncSession = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(import_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Invalid import ID format")
        
    stmt = select(ImportJobModel).where(ImportJobModel.id == job_uuid, ImportJobModel.tenant_id == tenant_id)
    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    
    if not job:
        raise HTTPException(status_code=404, detail="Import job not found")
        
    return {
        "id": str(job.id),
        "filename": job.filename,
        "format": job.format,
        "status": job.status,
        "records_received": job.records_received,
        "records_parsed": job.records_parsed,
        "parse_failed": job.parse_failed,
        "raw_records_stored": job.raw_records_stored,
        "normalized": job.normalized,
        "normalization_failed": job.normalization_failed,
        "unsupported": job.unsupported,
        "error_message": job.error_message
    }


# Helper to convert DB model to Pydantic, excluding raw_event
def _db_to_pydantic(db_model: NormalizedAlertModel) -> Dict[str, Any]:
    from datetime import datetime, timezone
    data = {c.name: getattr(db_model, c.name) for c in db_model.__table__.columns}
    data["id"] = str(data["id"])
    data["raw_event_id"] = str(data["raw_event_id"])
    
    # SQLite strips timezone info, re-attach UTC for Pydantic AwareDatetime validation
    for key in ["timestamp", "ingested_at"]:
        if isinstance(data.get(key), datetime) and data[key].tzinfo is None:
            data[key] = data[key].replace(tzinfo=timezone.utc)
            
    # We must exclude raw_event as it doesn't exist in the DB model anyway,
    # and the API shouldn't return it. But the Pydantic schema expects raw_event for runtime.
    # The requirement is that GET /alerts returns fields WITHOUT raw_event.
    return data

@router.get("/alerts")
async def list_alerts(tenant_id: str, db: AsyncSession = Depends(get_db)):
    stmt = select(NormalizedAlertModel).where(NormalizedAlertModel.tenant_id == tenant_id)
    result = await db.execute(stmt)
    alerts = result.scalars().all()
    return [_db_to_pydantic(a) for a in alerts]

@router.get("/alerts/{alert_id}")
async def get_alert(alert_id: str, tenant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        alert_uuid = uuid.UUID(alert_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Alert not found")
        
    stmt = select(NormalizedAlertModel).where(
        NormalizedAlertModel.id == alert_uuid,
        NormalizedAlertModel.tenant_id == tenant_id
    )
    result = await db.execute(stmt)
    alert = result.scalars().first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _db_to_pydantic(alert)

@router.post("/privacy/safe-evidence")
async def create_safe_evidence(request: SafeEvidenceRequest, db: AsyncSession = Depends(get_db)):
    # 1. Load tenant-scoped normalized alerts
    try:
        alert_uuids = [uuid.UUID(aid) for aid in request.alert_ids]
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid alert ID format")
        
    stmt = select(NormalizedAlertModel).where(
        NormalizedAlertModel.id.in_(alert_uuids),
        NormalizedAlertModel.tenant_id == request.tenant_id
    )
    result = await db.execute(stmt)
    db_alerts = result.scalars().all()

    
    if not db_alerts:
        raise HTTPException(status_code=404, detail="No matching alerts found for tenant")

    # Reconstruct NormalizedAlert objects for the Gateway
    runtime_alerts = []
    for db_alert in db_alerts:
        data = _db_to_pydantic(db_alert)
        # We supply an empty raw_event because Phase 1 Normalizers expected it,
        # but the DB deliberately omits it. The Gateway does not inspect raw_event,
        # only the normalized fields.
        data["raw_event"] = {} 
        runtime_alerts.append(NormalizedAlert(**data))

    # 2. Run Privacy Gateway
    gateway = LocalPrivacyGateway()
    try:
        # strictly external policy
        package, _, _ = gateway.process(runtime_alerts, PrivacyPolicy.strict_external())
    except Exception as e:
        raise HTTPException(status_code=500, detail="Privacy Gateway failed to process safely")

    # 3. Return ONLY SafeEvidencePackage
    return package
