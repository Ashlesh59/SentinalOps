from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func

from src.db.database import engine, async_session
from src.db.models import Base, NormalizedAlertModel
from src.api.demo import run_demo_attack_chain
from src.api.routes import router
from src.api.correlation import router as correlation_router
from src.api.incidents import router as incidents_router
from src.api.investigations import router as investigations_router
from src.api.dashboard import router as dashboard_router
from src.api.demo import router as demo_router
from src.api.system import router as system_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Auto-seed demo data if empty
    async with async_session() as session:
        try:
            count = await session.scalar(
                select(func.count(NormalizedAlertModel.id)).where(NormalizedAlertModel.tenant_id == "tenant-test")
            )
            if not count or count == 0:
                await run_demo_attack_chain(session)
                print("Demo attack chain auto-seeded successfully.")
        except Exception as e:
            print(f"Startup error: {e}")
    yield

app = FastAPI(
    title="SentinelOps API",
    description="Privacy-aware vendor-neutral SOC intelligence layer",
    version="0.3.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(correlation_router, prefix="/api/v1")
app.include_router(incidents_router, prefix="/api/v1")
app.include_router(investigations_router, prefix="/api/v1")
app.include_router(dashboard_router)
app.include_router(demo_router)
app.include_router(system_router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
