import asyncio

import structlog
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from eop_api.core.config import settings
from eop_api.db.dependencies import DbSession
from eop_api.storage.minio_provider import MinIOStorageProvider

router = APIRouter(tags=["Health"])
logger = structlog.get_logger(__name__)


async def _check_storage() -> bool:
    """Verify MinIO connectivity using the same `bucket_exists` primitive
    `MinIOStorageProvider` already relies on internally (`_ensure_bucket`).
    Connection failures surface as `urllib3` errors, not `MinioException`, so
    this catches broadly rather than risk missing a down server."""
    provider = MinIOStorageProvider(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )
    try:
        await asyncio.to_thread(provider._client.bucket_exists, settings.minio_bucket)
    except Exception:
        logger.exception("Storage health check failed")
        return False
    return True


@router.get("/health")
async def health(session: DbSession) -> JSONResponse:
    database_connected = True
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Database health check failed")
        database_connected = False

    storage_connected = await _check_storage()

    healthy = database_connected and storage_connected
    return JSONResponse(
        status_code=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ok" if healthy else "error",
            "database": "connected" if database_connected else "disconnected",
            "storage": "connected" if storage_connected else "disconnected",
            "version": settings.app_version,
            "environment": settings.environment,
        },
    )
