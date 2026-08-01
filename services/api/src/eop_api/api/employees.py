import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.schemas.employee import EmployeeCreate, EmployeeResponse, EmployeeUpdate
from eop_api.services.employee import (
    DuplicateEmployeeEmailError,
    EmployeeService,
    OrganizationNotFoundError,
)

router = APIRouter(prefix="/employees", tags=["Employees"])


def get_employee_service() -> EmployeeService:
    return EmployeeService()


EmployeeServiceDep = Annotated[EmployeeService, Depends(get_employee_service)]


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(data: EmployeeCreate, service: EmployeeServiceDep) -> EmployeeResponse:
    try:
        employee = await service.create(data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DuplicateEmployeeEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee email already exists",
        ) from exc
    return EmployeeResponse.model_validate(employee)


@router.get("", response_model=list[EmployeeResponse])
async def list_employees(service: EmployeeServiceDep) -> list[EmployeeResponse]:
    employees = await service.list()
    return [EmployeeResponse.model_validate(employee) for employee in employees]


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(employee_id: uuid.UUID, service: EmployeeServiceDep) -> EmployeeResponse:
    employee = await service.get(employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return EmployeeResponse.model_validate(employee)


@router.patch("/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    employee_id: uuid.UUID, data: EmployeeUpdate, service: EmployeeServiceDep
) -> EmployeeResponse:
    try:
        employee = await service.update(employee_id, data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
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
async def delete_employee(employee_id: uuid.UUID, service: EmployeeServiceDep) -> None:
    deleted = await service.delete(employee_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
