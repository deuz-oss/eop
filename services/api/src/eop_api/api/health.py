import structlog
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from eop_api.core.config import settings
from eop_api.db.dependencies import DbSession

router = APIRouter(tags=["Health"])
logger = structlog.get_logger(__name__)


@router.get("/health")
async def health(session: DbSession) -> JSONResponse:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "error",
                "database": "disconnected",
                "version": settings.app_version,
                "environment": settings.environment,
            },
        )

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "ok",
            "database": "connected",
            "version": settings.app_version,
            "environment": settings.environment,
        },
    )
