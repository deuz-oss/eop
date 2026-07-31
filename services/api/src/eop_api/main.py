from fastapi import FastAPI

from eop_api.api.health import router as health_router
from eop_api.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.include_router(health_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "application": settings.app_name,
        "version": "0.1.0",
        "environment": settings.environment,
        "status": "running",
    }
