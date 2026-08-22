from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db.models import Brain1ProcessingStateModel
import uuid
from datetime import datetime, timezone

class Brain1State:
    @staticmethod
    async def get_state(session: AsyncSession, tenant_id: str) -> Brain1ProcessingStateModel:
        result = await session.execute(
            select(Brain1ProcessingStateModel).where(Brain1ProcessingStateModel.tenant_id == tenant_id).with_for_update()
        )
        state = result.scalars().first()
        if not state:
            # PostgreSQL advisory locks will prevent concurrent inserts here in engine.py
            # But we can also handle it gracefully.
            state = Brain1ProcessingStateModel(
                tenant_id=tenant_id,
                last_processed_ingested_at=datetime(1970, 1, 1, tzinfo=timezone.utc),
                last_processed_alert_id=str(uuid.UUID(int=0)),
                correlation_rule_version="corr-v2"
            )
            session.add(state)
        return state

    @staticmethod
    def update_state(state: Brain1ProcessingStateModel, last_ingested_at: datetime, last_alert_id: str, rule_version: str):
        state.last_processed_ingested_at = last_ingested_at
        state.last_processed_alert_id = last_alert_id
        state.correlation_rule_version = rule_version
