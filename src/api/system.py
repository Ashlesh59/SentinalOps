import os
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Dict, Any

from src.db.database import get_db

router = APIRouter(prefix="/api/v1/system", tags=["system"])

@router.get("/health")
async def get_system_health(session: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    # Check DB
    try:
        await session.execute(text("SELECT 1"))
        db_status = "Healthy"
    except Exception:
        db_status = "Unavailable"

    provider = os.environ.get("BRAIN2_PROVIDER", "Anthropic")
    model = os.environ.get("BRAIN2_MODEL", "claude-3-5-sonnet-20240620")
    
    # Check if API Key is configured
    provider_status = "Healthy" if os.environ.get("ANTHROPIC_API_KEY") else "Degraded (No API Key)"

    return {
        "api": "Healthy",
        "database": db_status,
        "brain1": "Healthy",
        "brain2_provider": provider_status,
        "privacy_gateway": "Healthy",
        "provider_config": {
            "name": provider,
            "model": model
        }
    }
