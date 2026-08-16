import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.department import DepartmentCreate, DepartmentResponse, DepartmentUpdate
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.department import (
    CyclicParentDepartmentError,
    DepartmentService,
    DuplicateDepartmentCodeError,
    OrganizationNotFoundError,
    ParentDepartmentNotFoundError,
    ParentOrganizationMismatchError,
    SelfParentDepartmentError,
)

router = APIRouter(prefix="/departments", tags=["Departments"])


def get_department_service() -> DepartmentService:
    return DepartmentService()


DepartmentServiceDep = Annotated[DepartmentService, Depends(get_department_service)]


def get_department_filters(
    organization_id: Annotated[uuid.UUID | None, Query()] = None,
    parent_id: Annotated[uuid.UUID | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`organization_id`, `parent_id`), scoped to Departments."""
    values: dict[str, Any] = {}
    if organization_id is not None:
        values["organization_id"] = organization_id
    if parent_id is not None:
        values["parent_id"] = parent_id
    return FilterParams(values=values)


DepartmentFilters = Annotated[FilterParams, Depends(get_department_filters)]


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    data: DepartmentCreate, service: DepartmentServiceDep, _: CurrentUser
) -> DepartmentResponse:
    try:
        department = await service.create(data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except ParentDepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parent department not found"
        ) from exc
    except ParentOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parent department must belong to the same organization",
        ) from exc
    except DuplicateDepartmentCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department code already exists in this organization",
        ) from exc
    return DepartmentResponse.model_validate(department)


@router.get("", response_model=list[DepartmentResponse])
async def list_departments(
    service: DepartmentServiceDep, _: CurrentUser
) -> list[DepartmentResponse]:
    departments = await service.list()
    return [DepartmentResponse.model_validate(department) for department in departments]


@router.get("/paginated", response_model=Page[DepartmentResponse])
async def list_departments_paginated(
    service: DepartmentServiceDep,
    pagination: Pagination,
    search: Search,
    filters: DepartmentFilters,
    _: CurrentUser,
) -> Page[DepartmentResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[DepartmentResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{department_id}", response_model=DepartmentResponse)
async def get_department(
    department_id: uuid.UUID, service: DepartmentServiceDep, _: CurrentUser
) -> DepartmentResponse:
    department = await service.get(department_id)
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return DepartmentResponse.model_validate(department)


@router.put("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: uuid.UUID,
    data: DepartmentUpdate,
    service: DepartmentServiceDep,
    _: CurrentUser,
) -> DepartmentResponse:
    try:
        department = await service.update(department_id, data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except SelfParentDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A department cannot be its own parent",
        ) from exc
    except ParentDepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parent department not found"
        ) from exc
    except ParentOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parent department must belong to the same organization",
        ) from exc
    except CyclicParentDepartmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A department cannot be assigned a descendant as its parent",
        ) from exc
    except DuplicateDepartmentCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department code already exists in this organization",
        ) from exc
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
    return DepartmentResponse.model_validate(department)


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: uuid.UUID, service: DepartmentServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(department_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
