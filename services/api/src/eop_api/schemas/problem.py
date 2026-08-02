from typing import Any

from pydantic import BaseModel


class Problem(BaseModel):
    """RFC 9457 Problem Details for HTTP APIs."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    request_id: str | None = None


class ValidationProblem(Problem):
    """Problem Details for request validation failures, carrying per-field errors."""

    errors: list[dict[str, Any]]
