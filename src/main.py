from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import router
from src.api.correlation import router as correlation_router
from src.api.incidents import router as incidents_router
from src.api.investigations import router as investigations_router
from src.api.dashboard import router as dashboard_router
from src.api.demo import router as demo_router
from src.api.system import router as system_router

app = FastAPI(
    title="SentinelOps API",
    description="Privacy-aware vendor-neutral SOC intelligence layer",
    version="0.3.0"
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
