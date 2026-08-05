import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.schemas.timesheet import (
    TimesheetCreate,
    TimesheetRejectRequest,
    TimesheetResponse,
    TimesheetUpdate,
)
from eop_api.services.approval import (
    ApprovalAuthorizationDeniedError,
    ApprovalService,
    InvalidApprovalStateError,
)
from eop_api.services.timesheet import (
    EmployeeNotFoundError,
    InvalidTimesheetDateRangeError,
    TimesheetService,
)

router = APIRouter(prefix="/hr/timesheets", tags=["Timesheets"])


def get_timesheet_service() -> TimesheetService:
    return TimesheetService()


TimesheetServiceDep = Annotated[TimesheetService, Depends(get_timesheet_service)]


def get_approval_service() -> ApprovalService:
    return ApprovalService()


ApprovalServiceDep = Annotated[ApprovalService, Depends(get_approval_service)]


def get_timesheet_filters(
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`employee_id`, `status`, `start_date`, `end_date`),
    scoped to Timesheets."""
    values: dict[str, Any] = {}
    if employee_id is not None:
        values["employee_id"] = employee_id
    if status is not None:
        values["status"] = status
    if start_date is not None:
        values["start_date"] = start_date
    if end_date is not None:
        values["end_date"] = end_date
    return FilterParams(values=values)


TimesheetFilters = Annotated[FilterParams, Depends(get_timesheet_filters)]


@router.post("", response_model=TimesheetResponse, status_code=status.HTTP_201_CREATED)
async def create_timesheet(
    data: TimesheetCreate, service: TimesheetServiceDep, _: CurrentUser
) -> TimesheetResponse:
    try:
        timesheet = await service.create(data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except InvalidTimesheetDateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_date must not be before start_date",
        ) from exc
    return TimesheetResponse.model_validate(timesheet)


@router.get("", response_model=list[TimesheetResponse])
async def list_timesheets(
    service: TimesheetServiceDep, _: CurrentUser
) -> list[TimesheetResponse]:
    timesheets = await service.list()
    return [TimesheetResponse.model_validate(item) for item in timesheets]


@router.get("/paginated", response_model=Page[TimesheetResponse])
async def list_timesheets_paginated(
    service: TimesheetServiceDep,
    pagination: Pagination,
    search: Search,
    filters: TimesheetFilters,
    _: CurrentUser,
) -> Page[TimesheetResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[TimesheetResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{timesheet_id}", response_model=TimesheetResponse)
async def get_timesheet(
    timesheet_id: uuid.UUID, service: TimesheetServiceDep, _: CurrentUser
) -> TimesheetResponse:
    timesheet = await service.get(timesheet_id)
    if timesheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")
    return TimesheetResponse.model_validate(timesheet)


@router.put("/{timesheet_id}", response_model=TimesheetResponse)
async def update_timesheet(
    timesheet_id: uuid.UUID,
    data: TimesheetUpdate,
    service: TimesheetServiceDep,
    _: CurrentUser,
) -> TimesheetResponse:
    try:
        timesheet = await service.update(timesheet_id, data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except InvalidTimesheetDateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_date must not be before start_date",
        ) from exc
    if timesheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")
    return TimesheetResponse.model_validate(timesheet)


@router.delete("/{timesheet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_timesheet(
    timesheet_id: uuid.UUID, service: TimesheetServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(timesheet_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")


@router.post("/{timesheet_id}/approve", response_model=TimesheetResponse)
async def approve_timesheet(
    timesheet_id: uuid.UUID,
    service: ApprovalServiceDep,
    request_context: CurrentRequestContext,
) -> TimesheetResponse:
    try:
        timesheet = await service.approve_timesheet(timesheet_id, request_context)
    except ApprovalAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidApprovalStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if timesheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")
    return TimesheetResponse.model_validate(timesheet)


@router.post("/{timesheet_id}/reject", response_model=TimesheetResponse)
async def reject_timesheet(
    timesheet_id: uuid.UUID,
    data: TimesheetRejectRequest,
    service: ApprovalServiceDep,
    request_context: CurrentRequestContext,
) -> TimesheetResponse:
    try:
        timesheet = await service.reject_timesheet(timesheet_id, request_context, data.reason)
    except ApprovalAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidApprovalStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if timesheet is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Timesheet not found")
    return TimesheetResponse.model_validate(timesheet)
