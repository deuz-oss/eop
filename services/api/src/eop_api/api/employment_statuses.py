import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.employment_status import (
    EmploymentStatusCreate,
    EmploymentStatusResponse,
    EmploymentStatusUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.employment_status import (
    DuplicateEmploymentStatusCodeError,
    EmploymentStatusService,
)

router = APIRouter(prefix="/hr/employment-statuses", tags=["Employment Statuses"])


def get_employment_status_service() -> EmploymentStatusService:
    return EmploymentStatusService()


EmploymentStatusServiceDep = Annotated[
    EmploymentStatusService, Depends(get_employment_status_service)
]

# HR Master/Reference Data Authorization Policy: Role Based (`RequireRole("admin")`)
# for create/update/delete; reads remain open to any authenticated user.
# Reopened per CTO decision H2 (`HOLIDAY_CALENDAR_DESIGN.md` addendum) -- see
# `api/holidays.py`'s identical comment for the full rationale.
RequireHrMasterDataAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=EmploymentStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_employment_status(
    data: EmploymentStatusCreate, service: EmploymentStatusServiceDep, _: RequireHrMasterDataAdmin
) -> EmploymentStatusResponse:
    try:
        employment_status = await service.create(data)
    except DuplicateEmploymentStatusCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employment status code already exists",
        ) from exc
    return EmploymentStatusResponse.model_validate(employment_status)


@router.get("", response_model=list[EmploymentStatusResponse])
async def list_employment_statuses(
    service: EmploymentStatusServiceDep, _: CurrentUser
) -> list[EmploymentStatusResponse]:
    employment_statuses = await service.list()
    return [EmploymentStatusResponse.model_validate(item) for item in employment_statuses]


@router.get("/paginated", response_model=Page[EmploymentStatusResponse])
async def list_employment_statuses_paginated(
    service: EmploymentStatusServiceDep,
    pagination: Pagination,
    search: Search,
    _: CurrentUser,
) -> Page[EmploymentStatusResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[EmploymentStatusResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{employment_status_id}", response_model=EmploymentStatusResponse)
async def get_employment_status(
    employment_status_id: uuid.UUID, service: EmploymentStatusServiceDep, _: CurrentUser
) -> EmploymentStatusResponse:
    employment_status = await service.get(employment_status_id)
    if employment_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment status not found"
        )
    return EmploymentStatusResponse.model_validate(employment_status)


@router.put("/{employment_status_id}", response_model=EmploymentStatusResponse)
async def update_employment_status(
    employment_status_id: uuid.UUID,
    data: EmploymentStatusUpdate,
    service: EmploymentStatusServiceDep,
    _: RequireHrMasterDataAdmin,
) -> EmploymentStatusResponse:
    try:
        employment_status = await service.update(employment_status_id, data)
    except DuplicateEmploymentStatusCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employment status code already exists",
        ) from exc
    if employment_status is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment status not found"
        )
    return EmploymentStatusResponse.model_validate(employment_status)


@router.delete("/{employment_status_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employment_status(
    employment_status_id: uuid.UUID,
    service: EmploymentStatusServiceDep,
    _: RequireHrMasterDataAdmin,
) -> None:
    deleted = await service.delete(employment_status_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment status not found"
        )
