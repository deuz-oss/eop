"""Request-scoped identity propagated across the async call stack via ContextVar.

Populated by RequestIDMiddleware (request id) and, once authenticated, by the
auth dependency (user id). Readable from anywhere - services, repositories,
logging - without threading the Request object through every call.
"""

from contextvars import ContextVar, Token

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)


def current_request_id() -> str | None:
    return _request_id.get()


def current_user_id() -> str | None:
    return _user_id.get()


def bind_request_id(request_id: str) -> Token[str | None]:
    return _request_id.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    _request_id.reset(token)


def bind_user_id(user_id: str) -> Token[str | None]:
    return _user_id.set(user_id)


def reset_user_id(token: Token[str | None]) -> None:
    _user_id.reset(token)
