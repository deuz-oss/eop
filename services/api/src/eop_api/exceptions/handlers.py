import http

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from eop_api.core.logging import get_logger
from eop_api.core.problem import (
    forbidden_problem,
    not_found_problem,
    problem,
    unauthorized_problem,
    validation_problem,
)
from eop_api.middleware.request_id import REQUEST_ID_HEADER
from eop_api.schemas.problem import Problem

logger = get_logger(__name__)

PROBLEM_MEDIA_TYPE = "application/problem+json"

_PROBLEM_FACTORIES = {
    status.HTTP_401_UNAUTHORIZED: unauthorized_problem,
    status.HTTP_403_FORBIDDEN: forbidden_problem,
    status.HTTP_404_NOT_FOUND: not_found_problem,
}


def _build_http_problem(exc: StarletteHTTPException, instance: str) -> Problem:
    detail = exc.detail if isinstance(exc.detail, str) else None
    factory = _PROBLEM_FACTORIES.get(exc.status_code)
    if factory is not None:
        return factory(detail=detail, instance=instance)
    return problem(
        status_code=exc.status_code,
        title=http.HTTPStatus(exc.status_code).phrase,
        detail=detail,
        instance=instance,
    )


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Converts HTTPException (401/403/404/409/...) into an RFC 9457 Problem Details response."""
    assert isinstance(exc, StarletteHTTPException)

    problem_details = _build_http_problem(exc, instance=request.url.path)
    return JSONResponse(
        status_code=exc.status_code,
        content=problem_details.model_dump(mode="json", exclude_none=True),
        headers=exc.headers,
        media_type=PROBLEM_MEDIA_TYPE,
    )


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Converts request validation failures into an RFC 9457 Problem Details response,
    with per-field validation errors under `errors`.
    """
    assert isinstance(exc, RequestValidationError)

    problem_details = validation_problem(
        instance=request.url.path,
        errors=[
            {
                "loc": [str(part) for part in error["loc"]],
                "msg": error["msg"],
                "type": error["type"],
            }
            for error in exc.errors()
        ],
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=problem_details.model_dump(mode="json", exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Logs the full exception server-side and returns a safe, traceback-free Problem
    Details response.
    """
    # ServerErrorMiddleware sits outside RequestIDMiddleware, so by the time this runs
    # the request id contextvar has already been reset; request.state still has it.
    request_id = getattr(request.state, "request_id", None)

    logger.exception(
        "unhandled_exception",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    problem_details = Problem(
        title="Internal Server Error",
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal Server Error",
        instance=request.url.path,
        request_id=request_id,
    )

    # ServerErrorMiddleware sits outside RequestIDMiddleware, so the header must be
    # set here directly rather than relying on the middleware to attach it.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=problem_details.model_dump(mode="json", exclude_none=True),
        headers={REQUEST_ID_HEADER: request_id} if request_id else None,
        media_type=PROBLEM_MEDIA_TYPE,
    )
