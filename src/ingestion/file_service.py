import uuid
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.db.models import ImportJobModel, ImportJobStatus
from src.ingestion.format_detector import FormatDetector
from src.ingestion.parsers.registry import ParserRegistry
from src.ingestion.parsers.base import ParseError
from src.services.ingestion import IngestionService
from src.brain1.engine import run_correlation

logger = logging.getLogger(__name__)

class FileImportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ingestion_service = IngestionService(db)

    async def create_import_job(self, tenant_id: str, filename: str) -> str:
        job = ImportJobModel(
            tenant_id=tenant_id,
            filename=filename,
            format="UNKNOWN",
            status=ImportJobStatus.PENDING
        )
        self.db.add(job)
        await self.db.commit()
        return str(job.id)

    async def process_file(
        self, 
        job_id: str, 
        tenant_id: str, 
        content: bytes, 
        filename: str, 
        source_hint: Optional[str] = None
    ) -> None:
        """
        Background/Synchronous processor for file uploads.
        Updates ImportJobModel status incrementally.
        """
        # Load job
        stmt = select(ImportJobModel).where(ImportJobModel.id == uuid.UUID(job_id), ImportJobModel.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            logger.error(f"Import job {job_id} not found")
            return

        job.status = ImportJobStatus.PROCESSING
        await self.db.commit()
        await self.db.refresh(job)

        # 1. Format Detection
        try:
            detected_format = FormatDetector.detect(filename, content[:1024])
            job.format = detected_format
            await self.db.commit()
            await self.db.refresh(job)
            
            if detected_format == "UNKNOWN":
                job.status = ImportJobStatus.FAILED
                job.error_message = "Could not detect format"
                await self.db.commit()
                return

            # 2. Parsing
            parser = ParserRegistry.get_parser(detected_format)
            raw_events = parser.parse(content)
            job.records_received = len(raw_events)
            job.records_parsed = len(raw_events)
            await self.db.commit()
            await self.db.refresh(job)
            
        except ParseError as e:
            job.status = ImportJobStatus.FAILED
            job.error_message = f"Parsing failed: {str(e)}"
            await self.db.commit()
            return
        except Exception as e:
            job.status = ImportJobStatus.FAILED
            job.error_message = f"Unexpected error during parsing: {str(e)}"
            await self.db.commit()
            return

        # 3. Processing each record
        source_type = source_hint if source_hint else "UNKNOWN"
        
        raw_records_stored = 0
        normalized = 0
        normalization_failed = 0
        unsupported = 0
        parse_failed = 0
        
        for raw_payload in raw_events:
            try:
                proc_status, raw_id, norm_id_or_err = await self.ingestion_service.ingest_event(
                    tenant_id=tenant_id,
                    source_type=source_type,
                    source_vendor=raw_payload.get("vendor", "UnknownVendor"),
                    source_product=raw_payload.get("product", "UnknownProduct"),
                    payload=raw_payload
                )
                
                # Update metrics
                if proc_status in ("NORMALIZED", "NORMALIZATION_FAILED"):
                    raw_records_stored += 1
                    
                if proc_status == "NORMALIZED":
                    normalized += 1
                elif proc_status == "NORMALIZATION_FAILED":
                    normalization_failed += 1
                    # If it's literally just unsupported because no normalizer is there
                    if "No normalizer found" in str(norm_id_or_err):
                        unsupported += 1
                elif proc_status == "PERSISTENCE_FAILED":
                    parse_failed += 1  # We count persistence fail as a record processing fail
                    
            except Exception as e:
                # Catch-all for unexpected DB errors per row
                parse_failed += 1

        # Re-fetch job before final update to avoid expiration issues
        result = await self.db.execute(select(ImportJobModel).where(ImportJobModel.id == uuid.UUID(job_id)))
        job = result.scalar_one()

        job.raw_records_stored = raw_records_stored
        job.normalized = normalized
        job.normalization_failed = normalization_failed
        job.unsupported = unsupported
        job.parse_failed = parse_failed

        # 4. Final Status Evaluation
        if job.parse_failed > 0 or job.normalization_failed > 0:
            if job.normalized > 0 or job.raw_records_stored > 0:
                job.status = ImportJobStatus.PARTIAL
            else:
                job.status = ImportJobStatus.FAILED
                job.error_message = "All records failed to process."
        else:
            job.status = ImportJobStatus.COMPLETED

        await self.db.commit()

        # Auto-run Brain 1 correlation if any records were successfully processed.
        # This reuses the same run_correlation call used by the demo scenario.
        if job.normalized > 0:
            try:
                await run_correlation(self.db, tenant_id)
            except Exception as e:
                logger.error(f"Brain 1 correlation failed after import {job_id}: {e}")
                # Do not fail the import job — raw evidence is already persisted.
