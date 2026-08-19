import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.employment_type import (
    EmploymentTypeCreate,
    EmploymentTypeResponse,
    EmploymentTypeUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.employment_type import (
    DuplicateEmploymentTypeCodeError,
    EmploymentTypeService,
)

router = APIRouter(prefix="/hr/employment-types", tags=["Employment Types"])


def get_employment_type_service() -> EmploymentTypeService:
    return EmploymentTypeService()


EmploymentTypeServiceDep = Annotated[EmploymentTypeService, Depends(get_employment_type_service)]

# HR Master/Reference Data Authorization Policy: Role Based (`RequireRole("admin")`)
# for create/update/delete; reads remain open to any authenticated user.
# Reopened per CTO decision H2 (`HOLIDAY_CALENDAR_DESIGN.md` addendum) -- see
# `api/holidays.py`'s identical comment for the full rationale.
RequireHrMasterDataAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=EmploymentTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_employment_type(
    data: EmploymentTypeCreate, service: EmploymentTypeServiceDep, _: RequireHrMasterDataAdmin
) -> EmploymentTypeResponse:
    try:
        employment_type = await service.create(data)
    except DuplicateEmploymentTypeCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employment type code already exists",
        ) from exc
    return EmploymentTypeResponse.model_validate(employment_type)


@router.get("", response_model=list[EmploymentTypeResponse])
async def list_employment_types(
    service: EmploymentTypeServiceDep, _: CurrentUser
) -> list[EmploymentTypeResponse]:
    employment_types = await service.list()
    return [EmploymentTypeResponse.model_validate(item) for item in employment_types]


@router.get("/paginated", response_model=Page[EmploymentTypeResponse])
async def list_employment_types_paginated(
    service: EmploymentTypeServiceDep,
    pagination: Pagination,
    search: Search,
    _: CurrentUser,
) -> Page[EmploymentTypeResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[EmploymentTypeResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{employment_type_id}", response_model=EmploymentTypeResponse)
async def get_employment_type(
    employment_type_id: uuid.UUID, service: EmploymentTypeServiceDep, _: CurrentUser
) -> EmploymentTypeResponse:
    employment_type = await service.get(employment_type_id)
    if employment_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment type not found"
        )
    return EmploymentTypeResponse.model_validate(employment_type)


@router.put("/{employment_type_id}", response_model=EmploymentTypeResponse)
async def update_employment_type(
    employment_type_id: uuid.UUID,
    data: EmploymentTypeUpdate,
    service: EmploymentTypeServiceDep,
    _: RequireHrMasterDataAdmin,
) -> EmploymentTypeResponse:
    try:
        employment_type = await service.update(employment_type_id, data)
    except DuplicateEmploymentTypeCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employment type code already exists",
        ) from exc
    if employment_type is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment type not found"
        )
    return EmploymentTypeResponse.model_validate(employment_type)


@router.delete("/{employment_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_employment_type(
    employment_type_id: uuid.UUID, service: EmploymentTypeServiceDep, _: RequireHrMasterDataAdmin
) -> None:
    deleted = await service.delete(employment_type_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment type not found"
        )
