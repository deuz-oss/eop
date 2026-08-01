from fastapi import Request
from fastapi.responses import JSONResponse

from eop_api.core.logging import get_logger
from eop_api.middleware.request_id import REQUEST_ID_HEADER

logger = get_logger(__name__)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Logs the full exception server-side and returns a safe, traceback-free response."""
    request_id = getattr(request.state, "request_id", None)

    logger.exception(
        "unhandled_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    # ServerErrorMiddleware sits outside RequestIDMiddleware, so the header must be
    # set here directly rather than relying on the middleware to attach it.
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error", "request_id": request_id},
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
    )
