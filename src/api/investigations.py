import uuid
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from src.db.database import get_db, async_session
from src.db.models import IncidentModel, InvestigationJobModel, InvestigationResultModel, JobStatus
from src.brain2.selector import EvidenceSelector
from src.brain1.snapshot import SnapshotBuilder
from src.brain2.worker import Brain2Worker
from src.brain2.provider import get_provider

router = APIRouter()

class CreateInvestigationRequest(BaseModel):
    force: bool = False

async def run_worker_for_job(job_id: uuid.UUID):
    async with async_session() as session:
        job = (await session.execute(select(InvestigationJobModel).where(InvestigationJobModel.id == job_id))).scalars().first()
        if job and job.status == JobStatus.PENDING:
            worker = Brain2Worker(session=session, provider=get_provider())
            await worker.execute_job(job)

@router.post("/incidents/{incident_id}/investigations", status_code=status.HTTP_202_ACCEPTED)
async def create_investigation(
    incident_id: str,
    tenant_id: str,
    background_tasks: BackgroundTasks,
    req: CreateInvestigationRequest = CreateInvestigationRequest(),
    db: AsyncSession = Depends(get_db)
):
    try:
        inc_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")
        
    inc = (await db.execute(select(IncidentModel).where(IncidentModel.id == inc_uuid, IncidentModel.tenant_id == tenant_id))).scalars().first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    # generate fingerprint for cache check
    builder = SnapshotBuilder(session=db, tenant_id=tenant_id)
    snapshot = await builder.build_snapshot(inc_uuid)
    
    selector = EvidenceSelector()
    package = await selector.extract_package(snapshot)
    fingerprint = package.package_fingerprint
    
    if not req.force:
        # Check cache
        cache_stmt = (
            select(InvestigationJobModel)
            .where(
                InvestigationJobModel.incident_id == inc.id,
                InvestigationJobModel.tenant_id == tenant_id,
                InvestigationJobModel.safe_package_fingerprint == fingerprint,
                InvestigationJobModel.status == JobStatus.SUCCEEDED
            )
            .order_by(desc(InvestigationJobModel.id))
            .limit(1)
        )
        existing = (await db.execute(cache_stmt)).scalars().first()
        if existing:
            return {"job_id": str(existing.id), "status": existing.status, "message": "Reused existing investigation"}
            
    # Queue new job
    job = InvestigationJobModel(
        tenant_id=tenant_id,
        incident_id=inc.id,
        incident_version=inc.version,
        safe_package_fingerprint=fingerprint,
        status=JobStatus.PENDING
    )
    db.add(job)
    await db.commit()
    
    # Schedule background execution immediately
    background_tasks.add_task(run_worker_for_job, job.id)
    
    return {"job_id": str(job.id), "status": job.status, "message": "Investigation queued"}


@router.get("/incidents/{incident_id}/investigations/latest")
async def get_latest_investigation(incident_id: str, tenant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        inc_uuid = uuid.UUID(incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident ID format")
        
    # verify incident exists for tenant
    inc = (await db.execute(select(IncidentModel).where(IncidentModel.id == inc_uuid, IncidentModel.tenant_id == tenant_id))).scalars().first()
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
        
    job_stmt = select(InvestigationJobModel).where(InvestigationJobModel.incident_id == inc_uuid, InvestigationJobModel.tenant_id == tenant_id).order_by(desc(InvestigationJobModel.id)).limit(1)
    latest_job = (await db.execute(job_stmt)).scalars().first()
    
    if not latest_job:
        raise HTTPException(status_code=404, detail="No investigations found for this incident")
        
    res_stmt = select(InvestigationResultModel).where(InvestigationResultModel.incident_id == inc_uuid, InvestigationResultModel.tenant_id == tenant_id).order_by(desc(InvestigationResultModel.id)).limit(1)
    result = (await db.execute(res_stmt)).scalars().first()
    
    out = {
        "job_id": str(latest_job.id),
        "job_status": latest_job.status,
        "is_stale": latest_job.incident_version < inc.version,
        "incident_version_analyzed": latest_job.incident_version,
        "fingerprint": latest_job.safe_package_fingerprint,
    }
    
    if result:
        out.update({
            "result_id": str(result.id),
            "primary_hypothesis": result.primary_hypothesis,
            "incident_narrative": result.incident_narrative or "",
            "supporting_evidence": result.supporting_evidence or [],
            "contradicting_evidence": result.contradicting_evidence or [],
            "missing_evidence": result.missing_evidence or [],
            "recommended_disposition": result.recommended_disposition,
            "confidence": result.confidence if result.confidence is not None else 85,
            "recommended_priority": result.recommended_priority,
            "estimated_impact": result.estimated_impact or "HIGH",
            "confidence_drivers": result.confidence_drivers or [],
            "confidence_reducers": result.confidence_reducers or [],
            "next_best_actions": result.next_best_actions or [],
            "response_considerations": result.response_considerations or [],
            "attack_hypotheses": result.attack_hypotheses or [],
            "limitations": result.limitations or "None"
        })
        
    return out


@router.get("/investigations/{investigation_id}")
async def get_investigation_status(investigation_id: str, tenant_id: str, db: AsyncSession = Depends(get_db)):
    try:
        job_uuid = uuid.UUID(investigation_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid investigation ID format")
        
    job = (await db.execute(select(InvestigationJobModel).where(InvestigationJobModel.id == job_uuid, InvestigationJobModel.tenant_id == tenant_id))).scalars().first()
    if not job:
        raise HTTPException(status_code=404, detail="Investigation job not found")
        
    return {
        "job_id": str(job.id),
        "incident_id": str(job.incident_id),
        "status": job.status,
        "incident_version": job.incident_version,
        "worker_id": job.worker_id
    }
