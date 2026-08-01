import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.rbac import RequireRole
from eop_api.schemas.role import RoleCreate, RoleResponse, RoleUpdate
from eop_api.services.role import (
    DuplicateRoleAssignmentError,
    DuplicateRoleNameError,
    RoleNotFoundError,
    RoleService,
    UserNotFoundError,
)

router = APIRouter(prefix="/roles", tags=["Roles"])


def get_role_service() -> RoleService:
    return RoleService()


RoleServiceDep = Annotated[RoleService, Depends(get_role_service)]
RequireAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(data: RoleCreate, service: RoleServiceDep, _: RequireAdmin) -> RoleResponse:
    try:
        role = await service.create(data)
    except DuplicateRoleNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role name already exists"
        ) from exc
    return RoleResponse.model_validate(role)


@router.get("", response_model=list[RoleResponse])
async def list_roles(service: RoleServiceDep, _: CurrentUser) -> list[RoleResponse]:
    roles = await service.list()
    return [RoleResponse.model_validate(role) for role in roles]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(role_id: uuid.UUID, service: RoleServiceDep, _: CurrentUser) -> RoleResponse:
    role = await service.get(role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return RoleResponse.model_validate(role)


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: uuid.UUID, data: RoleUpdate, service: RoleServiceDep, _: RequireAdmin
) -> RoleResponse:
    try:
        role = await service.update(role_id, data)
    except DuplicateRoleNameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Role name already exists"
        ) from exc
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    return RoleResponse.model_validate(role)


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(role_id: uuid.UUID, service: RoleServiceDep, _: RequireAdmin) -> None:
    deleted = await service.delete(role_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")


@router.post("/{role_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def assign_role(
    role_id: uuid.UUID, user_id: uuid.UUID, service: RoleServiceDep, _: RequireAdmin
) -> None:
    try:
        await service.assign_role(role_id, user_id)
    except RoleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found") from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except DuplicateRoleAssignmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="User already has this role"
        ) from exc


@router.delete("/{role_id}/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(
    role_id: uuid.UUID, user_id: uuid.UUID, service: RoleServiceDep, _: RequireAdmin
) -> None:
    try:
        removed = await service.remove_role(role_id, user_id)
    except RoleNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found") from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User does not have this role"
        )
