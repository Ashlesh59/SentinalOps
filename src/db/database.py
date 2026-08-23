import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool

# Default to SQLite for easy local dev, or read from DATABASE_URL if PostgreSQL is configured
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./sentinelops.db"
)

# SQLite does not support poolclass=NullPool in same way with asyncpg options, NullPool works nicely
engine = create_async_engine(DATABASE_URL, echo=False, poolclass=NullPool)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

