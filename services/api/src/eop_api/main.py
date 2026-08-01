from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from eop_api.api.health import router as health_router
from eop_api.core.config import settings
from eop_api.core.logging import configure_logging
from eop_api.db.engine import engine

configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    logger.info("Database initialized")
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(health_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }
