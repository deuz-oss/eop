import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.exceptions.department import DepartmentOrganizationMismatchError
from eop_api.schemas.hr_employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.hr_employee import (
    DepartmentNotFoundError,
    DuplicateEmployeeEmailError,
    DuplicateEmployeeNumberError,
    EmploymentStatusNotFoundError,
    EmploymentTypeNotFoundError,
    HrEmployeeService,
    JobGradeNotFoundError,
    LocationNotFoundError,
    ManagerNotFoundError,
    OrganizationNotFoundError,
    PositionNotFoundError,
    PositionOrganizationMismatchError,
    SelfManagerError,
    ShiftNotFoundError,
    TeamDepartmentMismatchError,
    TeamNotFoundError,
    TeamOrganizationMismatchError,
)

router = APIRouter(prefix="/hr/employees", tags=["HR Employees"])


def get_hr_employee_service() -> HrEmployeeService:
    return HrEmployeeService()


HrEmployeeServiceDep = Annotated[HrEmployeeService, Depends(get_hr_employee_service)]


def get_hr_employee_filters(
    organization_id: Annotated[uuid.UUID | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    position_id: Annotated[uuid.UUID | None, Query()] = None,
    team_id: Annotated[uuid.UUID | None, Query()] = None,
    location_id: Annotated[uuid.UUID | None, Query()] = None,
    employment_status: Annotated[str | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`organization_id`, `department_id`, `position_id`,
    `team_id`, `location_id`, `employment_status`), scoped to HR Employees."""
    values: dict[str, Any] = {}
    if organization_id is not None:
        values["organization_id"] = organization_id
    if department_id is not None:
        values["department_id"] = department_id
    if position_id is not None:
        values["position_id"] = position_id
    if team_id is not None:
        values["team_id"] = team_id
    if location_id is not None:
        values["location_id"] = location_id
    if employment_status is not None:
        values["employment_status"] = employment_status
    return FilterParams(values=values)


HrEmployeeFilters = Annotated[FilterParams, Depends(get_hr_employee_filters)]


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_hr_employee(
    data: EmployeeCreate, service: HrEmployeeServiceDep, _: CurrentUser
) -> EmployeeResponse:
    try:
        employee = await service.create(data)
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
    except PositionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Position not found"
        ) from exc
    except PositionOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Position must belong to the same organization",
        ) from exc
    except TeamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found") from exc
    except TeamOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Team must belong to the same organization",
        ) from exc
    except TeamDepartmentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Team must belong to the same department",
        ) from exc
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Location not found"
        ) from exc
    except JobGradeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job grade not found"
        ) from exc
    except EmploymentTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment type not found"
        ) from exc
    except EmploymentStatusNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment status not found"
        ) from exc
    except ShiftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found"
        ) from exc
    except ManagerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found"
        ) from exc
    except DuplicateEmployeeNumberError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee number already exists",
        ) from exc
    except DuplicateEmployeeEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee email already exists",
        ) from exc
    return EmployeeResponse.model_validate(employee)


@router.get("", response_model=list[EmployeeResponse])
async def list_hr_employees(
    service: HrEmployeeServiceDep, _: CurrentUser
) -> list[EmployeeResponse]:
    employees = await service.list()
    return [EmployeeResponse.model_validate(employee) for employee in employees]


@router.get("/paginated", response_model=Page[EmployeeResponse])
async def list_hr_employees_paginated(
    service: HrEmployeeServiceDep,
    pagination: Pagination,
    search: Search,
    filters: HrEmployeeFilters,
    _: CurrentUser,
) -> Page[EmployeeResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[EmployeeResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_hr_employee(
    employee_id: uuid.UUID, service: HrEmployeeServiceDep, _: CurrentUser
) -> EmployeeResponse:
    employee = await service.get(employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return EmployeeResponse.model_validate(employee)


@router.put("/{employee_id}", response_model=EmployeeResponse)
async def update_hr_employee(
    employee_id: uuid.UUID,
    data: EmployeeUpdate,
    service: HrEmployeeServiceDep,
    _: CurrentUser,
) -> EmployeeResponse:
    try:
        employee = await service.update(employee_id, data)
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
    except PositionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Position not found"
        ) from exc
    except PositionOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Position must belong to the same organization",
        ) from exc
    except TeamNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found") from exc
    except TeamOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Team must belong to the same organization",
        ) from exc
    except TeamDepartmentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Team must belong to the same department",
        ) from exc
    except LocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Location not found"
        ) from exc
    except JobGradeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job grade not found"
        ) from exc
    except EmploymentTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment type not found"
        ) from exc
    except EmploymentStatusNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employment status not found"
        ) from exc
    except ShiftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found"
        ) from exc
    except SelfManagerError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An employee cannot be their own manager",
        ) from exc
    except ManagerNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Manager not found"
        ) from exc
    except DuplicateEmployeeNumberError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee number already exists",
        ) from exc
    except DuplicateEmployeeEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee email already exists",
        ) from exc
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return EmployeeResponse.model_validate(employee)


@router.delete("/{employee_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_hr_employee(
    employee_id: uuid.UUID, service: HrEmployeeServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(employee_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
