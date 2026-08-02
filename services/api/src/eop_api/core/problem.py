"""Factory helpers for building RFC 9457 Problem Details models.

These helpers only construct `Problem` models - callers are responsible for
turning them into an HTTP response.
"""

from typing import Any

from eop_api.core.request_context import current_request_id
from eop_api.schemas.problem import Problem, ValidationProblem

_DEFAULT_TYPE = "about:blank"


def problem(
    *,
    status_code: int,
    title: str,
    type: str = _DEFAULT_TYPE,
    detail: str | None = None,
    instance: str | None = None,
) -> Problem:
    return Problem(
        type=type,
        title=title,
        status=status_code,
        detail=detail,
        instance=instance,
        request_id=current_request_id(),
    )


def validation_problem(
    *,
    errors: list[dict[str, Any]],
    detail: str | None = "Request validation failed",
    instance: str | None = None,
) -> ValidationProblem:
    return ValidationProblem(
        type=_DEFAULT_TYPE,
        title="Unprocessable Entity",
        status=422,
        detail=detail,
        instance=instance,
        request_id=current_request_id(),
        errors=errors,
    )


def not_found_problem(*, detail: str | None = None, instance: str | None = None) -> Problem:
    return problem(status_code=404, title="Not Found", detail=detail, instance=instance)


def forbidden_problem(*, detail: str | None = None, instance: str | None = None) -> Problem:
    return problem(status_code=403, title="Forbidden", detail=detail, instance=instance)


def unauthorized_problem(*, detail: str | None = None, instance: str | None = None) -> Problem:
    return problem(status_code=401, title="Unauthorized", detail=detail, instance=instance)
