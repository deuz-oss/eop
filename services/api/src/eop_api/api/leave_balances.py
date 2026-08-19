import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.leave_balance import (
    LeaveBalanceCreate,
    LeaveBalanceResponse,
    LeaveBalanceUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.leave_balance import (
    EmployeeNotFoundError,
    InvalidLeaveBalanceError,
    LeaveBalanceService,
)

router = APIRouter(prefix="/hr/leave-balances", tags=["Leave Balances"])


def get_leave_balance_service() -> LeaveBalanceService:
    return LeaveBalanceService()


LeaveBalanceServiceDep = Annotated[LeaveBalanceService, Depends(get_leave_balance_service)]

# LeaveBalance Authorization Policy: Role Based (`RequireRole("admin")`) for
# create/update/delete; reads remain open to any authenticated user. Per CTO
# decision L2 -- LeaveBalance is administrative allocation data, not Owner
# Only. Reuses the same `RequireRole("admin")` mechanism `Location`/`Store`/
# `PayrollRun` already use; no `LeaveBalanceAuthorizationEvaluator` or other
# new authorization abstraction is introduced.
RequireLeaveBalanceAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


def get_leave_balance_filters(
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    period_year: Annotated[int | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`employee_id`, `period_year`), scoped to Leave Balances."""
    values: dict[str, Any] = {}
    if employee_id is not None:
        values["employee_id"] = employee_id
    if period_year is not None:
        values["period_year"] = period_year
    return FilterParams(values=values)


LeaveBalanceFilters = Annotated[FilterParams, Depends(get_leave_balance_filters)]


@router.post("", response_model=LeaveBalanceResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_balance(
    data: LeaveBalanceCreate, service: LeaveBalanceServiceDep, _: RequireLeaveBalanceAdmin
) -> LeaveBalanceResponse:
    try:
        leave_balance = await service.create(data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except InvalidLeaveBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="allocated_days, used_days, and remaining_days must be >= 0",
        ) from exc
    return LeaveBalanceResponse.model_validate(leave_balance)


@router.get("", response_model=list[LeaveBalanceResponse])
async def list_leave_balances(
    service: LeaveBalanceServiceDep, _: CurrentUser
) -> list[LeaveBalanceResponse]:
    leave_balances = await service.list()
    return [LeaveBalanceResponse.model_validate(item) for item in leave_balances]


@router.get("/paginated", response_model=Page[LeaveBalanceResponse])
async def list_leave_balances_paginated(
    service: LeaveBalanceServiceDep,
    pagination: Pagination,
    search: Search,
    filters: LeaveBalanceFilters,
    _: CurrentUser,
) -> Page[LeaveBalanceResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[LeaveBalanceResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{leave_balance_id}", response_model=LeaveBalanceResponse)
async def get_leave_balance(
    leave_balance_id: uuid.UUID, service: LeaveBalanceServiceDep, _: CurrentUser
) -> LeaveBalanceResponse:
    leave_balance = await service.get(leave_balance_id)
    if leave_balance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave balance not found")
    return LeaveBalanceResponse.model_validate(leave_balance)


@router.put("/{leave_balance_id}", response_model=LeaveBalanceResponse)
async def update_leave_balance(
    leave_balance_id: uuid.UUID,
    data: LeaveBalanceUpdate,
    service: LeaveBalanceServiceDep,
    _: RequireLeaveBalanceAdmin,
) -> LeaveBalanceResponse:
    try:
        leave_balance = await service.update(leave_balance_id, data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except InvalidLeaveBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="allocated_days, used_days, and remaining_days must be >= 0",
        ) from exc
    if leave_balance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave balance not found")
    return LeaveBalanceResponse.model_validate(leave_balance)


@router.delete("/{leave_balance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leave_balance(
    leave_balance_id: uuid.UUID, service: LeaveBalanceServiceDep, _: RequireLeaveBalanceAdmin
) -> None:
    deleted = await service.delete(leave_balance_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave balance not found")
