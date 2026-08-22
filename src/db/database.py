from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# For development, we'll use an in-memory SQLite DB for tests if needed,
# but default to the required PostgreSQL for Phase 3
DATABASE_URL = "postgresql+asyncpg://admin:supersecretpassword@localhost:5432/sentinelops"
# To allow running tests easily if postgres isn't spun up, we could use aiosqlite,
# but the requirements explicitly ask for postgres persistence.
# For unit tests, we'll swap the URL to sqlite+aiosqlite:///:memory:

from sqlalchemy.pool import NullPool
engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
