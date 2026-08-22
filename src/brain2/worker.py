import uuid
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from src.db.models import InvestigationJobModel, InvestigationRunModel, InvestigationResultModel, JobStatus, RunStatus, IncidentModel
from src.brain2.selector import EvidenceSelector
from src.brain2.provider import LLMProvider, TimeoutError
from src.brain2.validator import Brain2Validator, HallucinatedEvidenceError, ValidationCorrectionError
from src.brain2.schemas import InvestigationResultSchema

class Brain2Worker:
    def __init__(self, session: AsyncSession, provider: LLMProvider):
        self.session = session
        self.provider = provider
        self.validator = Brain2Validator()
        self.worker_id = str(uuid.uuid4())

    async def poll_and_claim_job(self) -> InvestigationJobModel:
        """
        Polls for a PENDING job and claims it using SKIP LOCKED semantics.
        """
        # For Postgres we could use with_for_update(skip_locked=True), but SQLite doesn't fully support it.
        # We will use it, assuming Postgres or a compatible backend.
        result = await self.session.scalars(
            select(InvestigationJobModel)
            .where(InvestigationJobModel.status == JobStatus.PENDING)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        job = result.first()
        
        if job:
            job.status = JobStatus.RUNNING
            job.worker_id = self.worker_id
            await self.session.commit()
        return job
        
    async def check_idempotency(self, tenant_id: str, incident_id: uuid.UUID, fingerprint: str) -> InvestigationResultModel:
        """
        Checks if we already have a SUCCESSFUL job with the same fingerprint.
        """
        result = await self.session.scalar(
            select(InvestigationResultModel)
            .join(InvestigationRunModel, InvestigationRunModel.id == InvestigationResultModel.run_id)
            .join(InvestigationJobModel, InvestigationJobModel.id == InvestigationRunModel.job_id)
            .where(
                InvestigationResultModel.tenant_id == tenant_id,
                InvestigationResultModel.incident_id == incident_id,
                InvestigationJobModel.safe_package_fingerprint == fingerprint,
                InvestigationRunModel.provider_name == self.provider.model_name,
                InvestigationRunModel.status == RunStatus.SUCCESS
            )
            .limit(1)
        )
        return result

    async def execute_job(self, job: InvestigationJobModel):
        print(f"[Brain 2] Worker {self.worker_id} executing Job {job.id}")
        
        # 1. Verify requested incident version
        incident = await self.session.scalar(
            select(IncidentModel)
            .where(IncidentModel.id == job.incident_id, IncidentModel.tenant_id == job.tenant_id)
        )
        if not incident:
            job.status = JobStatus.FAILED
            await self.session.commit()
            return
            
        if incident.version != job.incident_version:
            # The incident changed since the job was queued!
            job.status = JobStatus.STALE
            await self.session.commit()
            return

        # 2. Build Snapshot -> Evidence Selector -> Safe Package
        try:
            from src.brain1.snapshot import SnapshotBuilder
            builder = SnapshotBuilder(session=self.session, tenant_id=job.tenant_id)
            snapshot = await builder.build_snapshot(job.incident_id)
            
            selector = EvidenceSelector()
            package = await selector.extract_package(snapshot)
        except Exception as e:
            print(f"[Brain 2] Package extraction failed: {e}")
            job.status = JobStatus.FAILED
            await self.session.commit()
            return

        # Verify package fingerprint
        if package.package_fingerprint != job.safe_package_fingerprint:
            job.status = JobStatus.STALE
            await self.session.commit()
            return
            
        # 2.5 Cache / Idempotency check (unless force is true, but we don't have force in the job model yet. Assume not force)
        existing_result = await self.check_idempotency(job.tenant_id, job.incident_id, package.package_fingerprint)
        if existing_result:
            print(f"[Brain 2] Idempotency cache hit for Job {job.id}")
            job.status = JobStatus.SUCCEEDED
            await self.session.commit()
            return
            
        # 3. Create Investigation Run
        run = InvestigationRunModel(
            tenant_id=job.tenant_id,
            job_id=job.id,
            provider_name=self.provider.model_name,
            model_version="latest",
            brain2_policy_version="v1",
            status=RunStatus.FAILED # default until success
        )
        self.session.add(run)
        await self.session.flush()

        # 4. LLM Provider Execution + Validation Loop
        raw_json = None
        parsed_result = None
        run_status = RunStatus.FAILED
        
        try:
            raw_json = await self.provider.assess_incident(package, schema=InvestigationResultSchema)
            
            # 5. Validator
            parsed_result = self.validator.validate(raw_json, package)
            run_status = RunStatus.SUCCESS
            
        except TimeoutError:
            print("[Brain 2] Provider Timeout")
            run_status = RunStatus.FAILED_TIMEOUT
        except ValidationCorrectionError as e:
            print(f"[Brain 2] Validation Failed: {e}")
            run_status = RunStatus.FAILED_VALIDATION
        except HallucinatedEvidenceError as e:
            print(f"[Brain 2] Hallucination Detected: {e}")
            run_status = RunStatus.FAILED_VALIDATION
        except Exception as e:
            print(f"[Brain 2] Unknown Error: {e}")
            run_status = RunStatus.FAILED

        # 6. Finalize Run
        run.status = run_status
        run.ended_at = datetime.datetime.utcnow()
        
        # 7. Finalize Job
        if run_status == RunStatus.SUCCESS and parsed_result:
            result_model = InvestigationResultModel(
                tenant_id=job.tenant_id,
                run_id=run.id,
                incident_id=job.incident_id,
                primary_hypothesis=parsed_result.primary_hypothesis,
                incident_narrative=parsed_result.incident_narrative,
                supporting_evidence=[ev.model_dump() for ev in parsed_result.supporting_evidence],
                contradicting_evidence=[ev.model_dump() for ev in parsed_result.contradicting_evidence],
                missing_evidence=[ev.model_dump() for ev in parsed_result.missing_evidence],
                recommended_disposition=parsed_result.recommended_disposition,
                confidence=parsed_result.confidence,
                recommended_priority=parsed_result.recommended_priority,
                estimated_impact=parsed_result.estimated_impact,
                confidence_drivers=parsed_result.confidence_drivers,
                confidence_reducers=parsed_result.confidence_reducers,
                next_best_actions=[act.model_dump() for act in parsed_result.next_best_actions],
                response_considerations=parsed_result.response_considerations,
                attack_hypotheses=[hyp.model_dump() for hyp in parsed_result.attack_hypotheses],
                limitations=parsed_result.limitations
            )
            self.session.add(result_model)
            job.status = JobStatus.SUCCEEDED
        else:
            job.status = JobStatus.FAILED

        await self.session.commit()
        print(f"[Brain 2] Job {job.id} finalized with status {job.status}")
