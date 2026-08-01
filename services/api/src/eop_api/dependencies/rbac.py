from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.models.user import User
from eop_api.services.role import RoleService


def get_role_service() -> RoleService:
    return RoleService()


RoleServiceDep = Annotated[RoleService, Depends(get_role_service)]


def RequireRole(role_name: str) -> Callable[[User, RoleService], Awaitable[User]]:
    """Dependency factory: the current user must hold `role_name`, otherwise 403.

    Authentication is enforced upstream by `CurrentUser`; a missing/invalid
    token already yields 401 before this check ever runs.
    """

    async def dependency(current_user: CurrentUser, service: RoleServiceDep) -> User:
        if not await service.user_has_role(current_user.id, role_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role privileges",
            )
        return current_user

    return dependency
