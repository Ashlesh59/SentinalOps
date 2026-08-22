import asyncio
import time
import uuid
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import async_session
from src.db.models import RawEventModel, NormalizedAlertModel, AggregatedSignalModel, SignalEntityModel, CorrelationEdgeModel, IncidentModel, IncidentSignalModel, Brain1ProcessingStateModel
from src.brain1.engine import run_correlation

async def clean_db(session: AsyncSession, tenant_id: str):
    await session.execute(text("DELETE FROM correlation_edges WHERE tenant_id = :t"), {"t": tenant_id})
    await session.execute(text("DELETE FROM incident_signals WHERE incident_id IN (SELECT id FROM incidents WHERE tenant_id = :t)"), {"t": tenant_id})
    await session.execute(text("DELETE FROM incidents WHERE tenant_id = :t"), {"t": tenant_id})
    await session.execute(text("DELETE FROM signal_entities WHERE tenant_id = :t"), {"t": tenant_id})
    await session.execute(text("DELETE FROM aggregated_signal_alerts WHERE aggregated_signal_id IN (SELECT id FROM aggregated_signals WHERE tenant_id = :t)"), {"t": tenant_id})
    await session.execute(text("DELETE FROM aggregated_signals WHERE tenant_id = :t"), {"t": tenant_id})
    await session.execute(text("DELETE FROM normalized_alerts WHERE tenant_id = :t"), {"t": tenant_id})
    await session.execute(text("DELETE FROM raw_events WHERE tenant_id = :t"), {"t": tenant_id})
    await session.execute(text("DELETE FROM brain1_processing_state WHERE tenant_id = :t"), {"t": tenant_id})
    await session.commit()
    print(f"[{datetime.now().time()}] Cleaned DB for {tenant_id}")

async def test_1_limit_1000(session):
    print(f"[{datetime.now().time()}] Starting test 1")
    tenant = "tenant_adv"
    await clean_db(session, tenant)
    print(f"[{datetime.now().time()}] Inserting 1000 alerts")
    
    now = datetime.now(timezone.utc)
    raws = []
    alerts = []
    
    for i in range(1005):
        rid = uuid.uuid4()
        raws.append(RawEventModel(id=rid, tenant_id=tenant, source_type="xdr", source_vendor="CrowdStrike", source_product="Falcon", received_at=now, raw_payload={}))
        alerts.append(NormalizedAlertModel(id=uuid.uuid4(), raw_event_id=rid, tenant_id=tenant, source_event_id=f"evt-{i}", timestamp=now - timedelta(minutes=i), ingested_at=now, source_type="xdr", source_vendor="CrowdStrike", source_product="Falcon", category_name="Malware", class_name="Detection", alert_type="Malware", severity="HIGH", schema_version="1.0", host=f"host-{i}", file_hash="evil-hash-1"))
        
    session.add_all(raws)
    await session.flush()
    session.add_all(alerts)
    await session.commit()
    
    res = await run_correlation(session, tenant)
    print(f"TEST 1 (LIMIT 1000): {res['metrics']}")
    
async def test_2_late_aggregation(session):
    tenant = "tenant_late"
    await clean_db(session, tenant)
    
    now = datetime.now(timezone.utc)
    
    rid_a = uuid.uuid4()
    alert_a = NormalizedAlertModel(id=uuid.uuid4(), raw_event_id=rid_a, tenant_id=tenant, source_event_id="evt-a", timestamp=now, ingested_at=now, source_type="xdr", source_vendor="V", source_product="P", category_name="C", class_name="C", alert_type="A", severity="HIGH", schema_version="1.0", host="host-a")
    session.add(RawEventModel(id=rid_a, tenant_id=tenant, source_type="xdr", source_vendor="V", source_product="P", received_at=now, raw_payload={}))
    await session.flush()
    session.add(alert_a)
    await session.commit()
    await run_correlation(session, tenant) 
    
    rid_c = uuid.uuid4()
    alert_c = NormalizedAlertModel(id=uuid.uuid4(), raw_event_id=rid_c, tenant_id=tenant, source_event_id="evt-c", timestamp=now + timedelta(minutes=10), ingested_at=now, source_type="xdr", source_vendor="V", source_product="P", category_name="C", class_name="C", alert_type="A", severity="HIGH", schema_version="1.0", host="host-a")
    session.add(RawEventModel(id=rid_c, tenant_id=tenant, source_type="xdr", source_vendor="V", source_product="P", received_at=now, raw_payload={}))
    await session.flush()
    session.add(alert_c)
    await session.commit()
    await run_correlation(session, tenant) 
    
    sigs = (await session.execute(select(AggregatedSignalModel).where(AggregatedSignalModel.tenant_id==tenant))).scalars().all()
    sigs[0].last_seen = now - timedelta(hours=2) 
    await session.commit()
    
    rid_d = uuid.uuid4()
    alert_d = NormalizedAlertModel(id=uuid.uuid4(), raw_event_id=rid_d, tenant_id=tenant, source_event_id="evt-d", timestamp=now + timedelta(hours=1), ingested_at=now, source_type="xdr", source_vendor="V", source_product="P", category_name="C", class_name="C", alert_type="A", severity="HIGH", schema_version="1.0", host="host-a")
    session.add(RawEventModel(id=rid_d, tenant_id=tenant, source_type="xdr", source_vendor="V", source_product="P", received_at=now, raw_payload={}))
    await session.flush()
    session.add(alert_d)
    await session.commit()
    await run_correlation(session, tenant) 
    
    rid_b = uuid.uuid4()
    alert_b = NormalizedAlertModel(id=uuid.uuid4(), raw_event_id=rid_b, tenant_id=tenant, source_event_id="evt-b", timestamp=now + timedelta(minutes=5), ingested_at=now, source_type="xdr", source_vendor="V", source_product="P", category_name="C", class_name="C", alert_type="A", severity="HIGH", schema_version="1.0", host="host-a")
    session.add(RawEventModel(id=rid_b, tenant_id=tenant, source_type="xdr", source_vendor="V", source_product="P", received_at=now, raw_payload={}))
    await session.flush()
    session.add(alert_b)
    await session.commit()
    
    await run_correlation(session, tenant) 
    
    sigs = (await session.execute(select(AggregatedSignalModel).where(AggregatedSignalModel.tenant_id==tenant))).scalars().all()
    print(f"TEST 2 (Late Aggregation): Remaining Signals Count = {len(sigs)}. Alerts in signal = {sigs[0].occurrence_count}")

async def test_5_explain_analyze(session):
    tenant = "tenant_adv"
    explain_sql = text("""
        EXPLAIN (ANALYZE, BUFFERS) 
        SELECT aggregated_signal_id 
        FROM signal_entities 
        WHERE tenant_id = 'tenant_adv' 
          AND entity_type = 'HASH' 
          AND entity_value = 'evil-hash-1' 
          AND first_seen <= NOW() 
          AND last_seen >= NOW() - INTERVAL '2 hours' 
          AND aggregated_signal_id != '00000000-0000-0000-0000-000000000000' 
        ORDER BY last_seen DESC 
        LIMIT 1000
    """)
    res = await session.execute(explain_sql)
    print("TEST 5 (EXPLAIN ANALYZE):")
    for row in res.all():
        print(row[0])

async def test_scale(session, tenant, count):
    await clean_db(session, tenant)
    now = datetime.now(timezone.utc)
    raws = []
    alerts = []
    
    for i in range(count):
        rid = uuid.uuid4()
        raws.append(RawEventModel(id=rid, tenant_id=tenant, source_type="xdr", source_vendor="CrowdStrike", source_product="Falcon", received_at=now - timedelta(seconds=i), raw_payload={}))
        alerts.append(NormalizedAlertModel(id=uuid.uuid4(), raw_event_id=rid, tenant_id=tenant, source_event_id=f"evt-{i}", timestamp=now - timedelta(seconds=i), ingested_at=now, source_type="xdr", source_vendor="CrowdStrike", source_product="Falcon", category_name="Malware", class_name="Detection", alert_type="Malware", severity="HIGH", schema_version="1.0", host=f"host-{i%20}", file_hash=f"hash-{i%10}"))
        
    session.add_all(raws)
    await session.flush()
    session.add_all(alerts)
    await session.commit()
    
    res = await run_correlation(session, tenant)
    print(f"TEST SCALE {count}: {res['metrics']['run_duration_ms']:.2f} ms")
    
async def main():
    async with async_session() as session:
        print("Running Gate B Verification...")
        await test_1_limit_1000(session)
        await test_2_late_aggregation(session)
        await test_5_explain_analyze(session)
        
        await test_scale(session, "tenant_s100", 100)
        await test_scale(session, "tenant_s1k", 1000)
        await test_scale(session, "tenant_s10k", 10000)

if __name__ == "__main__":
    asyncio.run(main())
