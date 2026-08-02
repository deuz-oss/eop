import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.position import PositionCreate, PositionResponse, PositionUpdate
from eop_api.schemas.search import FilterParams
from eop_api.services.position import (
    DepartmentNotFoundError,
    DepartmentOrganizationMismatchError,
    DuplicatePositionCodeError,
    OrganizationNotFoundError,
    PositionService,
)

router = APIRouter(prefix="/positions", tags=["Positions"])


def get_position_service() -> PositionService:
    return PositionService()


PositionServiceDep = Annotated[PositionService, Depends(get_position_service)]


def get_position_filters(
    organization_id: Annotated[uuid.UUID | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`organization_id`, `department_id`), scoped to Positions."""
    values: dict[str, Any] = {}
    if organization_id is not None:
        values["organization_id"] = organization_id
    if department_id is not None:
        values["department_id"] = department_id
    return FilterParams(values=values)


PositionFilters = Annotated[FilterParams, Depends(get_position_filters)]


@router.post("", response_model=PositionResponse, status_code=status.HTTP_201_CREATED)
async def create_position(
    data: PositionCreate, service: PositionServiceDep, _: CurrentUser
) -> PositionResponse:
    try:
        position = await service.create(data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        ) from exc
    except DepartmentOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Department must belong to the same organization",
        ) from exc
    except DuplicatePositionCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Position code already exists in this organization",
        ) from exc
    return PositionResponse.model_validate(position)


@router.get("", response_model=list[PositionResponse])
async def list_positions(service: PositionServiceDep, _: CurrentUser) -> list[PositionResponse]:
    positions = await service.list()
    return [PositionResponse.model_validate(position) for position in positions]


@router.get("/paginated", response_model=Page[PositionResponse])
async def list_positions_paginated(
    service: PositionServiceDep,
    pagination: Pagination,
    search: Search,
    filters: PositionFilters,
    _: CurrentUser,
) -> Page[PositionResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[PositionResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{position_id}", response_model=PositionResponse)
async def get_position(
    position_id: uuid.UUID, service: PositionServiceDep, _: CurrentUser
) -> PositionResponse:
    position = await service.get(position_id)
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    return PositionResponse.model_validate(position)


@router.put("/{position_id}", response_model=PositionResponse)
async def update_position(
    position_id: uuid.UUID,
    data: PositionUpdate,
    service: PositionServiceDep,
    _: CurrentUser,
) -> PositionResponse:
    try:
        position = await service.update(position_id, data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        ) from exc
    except DepartmentOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Department must belong to the same organization",
        ) from exc
    except DuplicatePositionCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Position code already exists in this organization",
        ) from exc
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    return PositionResponse.model_validate(position)


@router.delete("/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_position(
    position_id: uuid.UUID, service: PositionServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(position_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
