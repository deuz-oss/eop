from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from eop_api.api.health import router as health_router
from eop_api.api.organizations import router as organizations_router
from eop_api.api.projects import router as projects_router
from eop_api.core.config import settings
from eop_api.core.logging import configure_logging
from eop_api.db.engine import engine
from eop_api.exceptions.handlers import unhandled_exception_handler
from eop_api.middleware.request_id import RequestIDMiddleware
from eop_api.middleware.request_logging import RequestLoggingMiddleware

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

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(health_router)
app.include_router(organizations_router)
app.include_router(projects_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "application": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "status": "running",
    }
