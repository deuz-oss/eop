from collections.abc import AsyncGenerator
from contextvars import Token
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from eop_api.core.request_context import bind_user_id, reset_user_id
from eop_api.models.user import User
from eop_api.services.auth import AuthService, InvalidTokenError

security = HTTPBearer()


def get_auth_service() -> AuthService:
    return AuthService()


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def bind_current_user(user: User) -> Token[str | None]:
    """Binds the authenticated user's id into the request context."""
    return bind_user_id(str(user.id))


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    service: AuthServiceDep,
) -> AsyncGenerator[User]:
    try:
        user = await service.get_current_user(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    token = bind_current_user(user)
    try:
        yield user
    finally:
        reset_user_id(token)


CurrentUser = Annotated[User, Depends(get_current_user)]
