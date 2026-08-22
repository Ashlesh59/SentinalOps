import asyncio
import time
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import async_session
from src.db.models import RawEventModel, NormalizedAlertModel
from src.brain1.engine import run_correlation

async def setup_benchmark_data(session: AsyncSession, tenant_id: str, count: int):
    # Insert bulk alerts
    alerts = []
    raws = []
    now = datetime.now(timezone.utc)
    for i in range(count):
        raw_id = uuid.uuid4()
        raws.append(RawEventModel(
            id=raw_id,
            tenant_id=tenant_id,
            source_type="xdr",
            source_vendor="CrowdStrike",
            source_product="Falcon",
            received_at=now - timedelta(minutes=i),
            raw_payload={}
        ))
        alerts.append(NormalizedAlertModel(
            id=uuid.uuid4(),
            raw_event_id=raw_id,
            tenant_id=tenant_id,
            source_event_id=f"evt-{i}",
            timestamp=now - timedelta(minutes=i),
            ingested_at=now,
            source_type="xdr",
            source_vendor="CrowdStrike",
            source_product="Falcon",
            category_name="Malware",
            class_name="Detection",
            alert_type="Malware",
            severity="HIGH",
            schema_version="1.0",
            host=f"host-{i%10}",
            file_hash=f"hash-{i%5}"
        ))
    session.add_all(raws)
    await session.flush()
    session.add_all(alerts)
    await session.commit()
    
async def run_benchmark():
    tenant_id = "tenant_benchmark"
    async with async_session() as session:
        # Clear previous data
        await session.execute(text("DELETE FROM correlation_edges WHERE tenant_id = :tenant"), {"tenant": tenant_id})
        await session.execute(text("DELETE FROM incident_signals WHERE incident_id IN (SELECT id FROM incidents WHERE tenant_id = :tenant)"), {"tenant": tenant_id})
        await session.execute(text("DELETE FROM incidents WHERE tenant_id = :tenant"), {"tenant": tenant_id})
        await session.execute(text("DELETE FROM signal_entities WHERE tenant_id = :tenant"), {"tenant": tenant_id})
        await session.execute(text("DELETE FROM aggregated_signal_alerts WHERE aggregated_signal_id IN (SELECT id FROM aggregated_signals WHERE tenant_id = :tenant)"), {"tenant": tenant_id})
        await session.execute(text("DELETE FROM aggregated_signals WHERE tenant_id = :tenant"), {"tenant": tenant_id})
        await session.execute(text("DELETE FROM normalized_alerts WHERE tenant_id = :tenant"), {"tenant": tenant_id})
        await session.execute(text("DELETE FROM raw_events WHERE tenant_id = :tenant"), {"tenant": tenant_id})
        await session.execute(text("DELETE FROM brain1_processing_state WHERE tenant_id = :tenant"), {"tenant": tenant_id})
        await session.commit()
        
        print("Setting up data (1000 alerts)...")
        await setup_benchmark_data(session, tenant_id, 1000)
        
        print("Running correlation engine benchmark...")
        start_time = time.perf_counter()
        result = await run_correlation(session, tenant_id)
        duration = time.perf_counter() - start_time
        
        print(f"Benchmark completed in {duration:.4f} seconds")
        print(f"Processed alerts: {result.get('processed_alerts')}")
        print(f"Metrics: {result.get('metrics')}")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
