from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from src.db.database import get_db
from src.brain1.engine import run_correlation

router = APIRouter()

class CorrelationRunRequest(BaseModel):
    tenant_id: str

@router.post("/correlation/run")
async def execute_correlation(request: CorrelationRunRequest, db: AsyncSession = Depends(get_db)):
    try:
        result = await run_correlation(db, request.tenant_id)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Correlation engine failed: {str(e)}")
