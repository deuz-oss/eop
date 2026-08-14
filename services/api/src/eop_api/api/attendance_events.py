import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.core.attendance import EventSource, EventType
from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.attendance_event import (
    AttendanceEventCreate,
    AttendanceEventResponse,
    AttendanceEventUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.attendance_event import (
    AttendanceAuthorizationDeniedError,
    AttendanceEventService,
    EmployeeNotFoundError,
    ShiftNotFoundError,
)

router = APIRouter(prefix="/hr/attendance-events", tags=["Attendance Events"])


def get_attendance_event_service() -> AttendanceEventService:
    return AttendanceEventService()


AttendanceEventServiceDep = Annotated[AttendanceEventService, Depends(get_attendance_event_service)]


def get_attendance_event_filters(
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    shift_id: Annotated[uuid.UUID | None, Query()] = None,
    event_type: Annotated[EventType | None, Query()] = None,
    source: Annotated[EventSource | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`employee_id`, `shift_id`, `event_type`, `source`),
    scoped to Attendance Events."""
    values: dict[str, Any] = {}
    if employee_id is not None:
        values["employee_id"] = employee_id
    if shift_id is not None:
        values["shift_id"] = shift_id
    if event_type is not None:
        values["event_type"] = event_type
    if source is not None:
        values["source"] = source
    return FilterParams(values=values)


AttendanceEventFilters = Annotated[FilterParams, Depends(get_attendance_event_filters)]


@router.post("", response_model=AttendanceEventResponse, status_code=status.HTTP_201_CREATED)
async def create_attendance_event(
    data: AttendanceEventCreate,
    service: AttendanceEventServiceDep,
    request_context: CurrentRequestContext,
) -> AttendanceEventResponse:
    try:
        event = await service.create(data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except ShiftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found"
        ) from exc
    except AttendanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return AttendanceEventResponse.model_validate(event)


@router.get("", response_model=list[AttendanceEventResponse])
async def list_attendance_events(
    service: AttendanceEventServiceDep, request_context: CurrentRequestContext
) -> list[AttendanceEventResponse]:
    events = await service.list(request_context)
    return [AttendanceEventResponse.model_validate(item) for item in events]


@router.get("/paginated", response_model=Page[AttendanceEventResponse])
async def list_attendance_events_paginated(
    service: AttendanceEventServiceDep,
    pagination: Pagination,
    search: Search,
    filters: AttendanceEventFilters,
    request_context: CurrentRequestContext,
) -> Page[AttendanceEventResponse]:
    page = await service.list_paginated(request_context, pagination, search, filters)
    return Page(
        items=[AttendanceEventResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{event_id}", response_model=AttendanceEventResponse)
async def get_attendance_event(
    event_id: uuid.UUID,
    service: AttendanceEventServiceDep,
    request_context: CurrentRequestContext,
) -> AttendanceEventResponse:
    try:
        event = await service.get(event_id, request_context)
    except AttendanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendance event not found"
        )
    return AttendanceEventResponse.model_validate(event)


@router.put("/{event_id}", response_model=AttendanceEventResponse)
async def update_attendance_event(
    event_id: uuid.UUID,
    data: AttendanceEventUpdate,
    service: AttendanceEventServiceDep,
    request_context: CurrentRequestContext,
) -> AttendanceEventResponse:
    try:
        event = await service.update(event_id, data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except ShiftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found"
        ) from exc
    except AttendanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendance event not found"
        )
    return AttendanceEventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attendance_event(
    event_id: uuid.UUID,
    service: AttendanceEventServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(event_id, request_context)
    except AttendanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attendance event not found"
        )
