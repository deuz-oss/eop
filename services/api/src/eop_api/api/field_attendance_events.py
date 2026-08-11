import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.core.field_attendance import FieldAttendanceEventType
from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.schemas.field_attendance_event import (
    FieldAttendanceEventCreate,
    FieldAttendanceEventResponse,
    FieldAttendanceEventUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.field_attendance_event import (
    EmployeeNotFoundError,
    FieldAttendanceAuthorizationDeniedError,
    FieldAttendanceEventService,
    SelfieFileNotFoundError,
)

router = APIRouter(prefix="/field-attendance", tags=["Field Attendance"])


def get_field_attendance_event_service() -> FieldAttendanceEventService:
    return FieldAttendanceEventService()


FieldAttendanceEventServiceDep = Annotated[
    FieldAttendanceEventService, Depends(get_field_attendance_event_service)
]


def get_field_attendance_filters(
    event_type: Annotated[FieldAttendanceEventType | None, Query()] = None,
    event_time: Annotated[datetime | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`event_type`/`event_time`), scoped to Field
    Attendance events. `employee_id` is deliberately not accepted here --
    it is always forced to the caller's own resolved employee id at the
    service layer, not exposed as a client-supplied filter."""
    values: dict[str, Any] = {}
    if event_type is not None:
        values["event_type"] = event_type
    if event_time is not None:
        values["event_time"] = event_time
    return FilterParams(values=values)


FieldAttendanceFilters = Annotated[FilterParams, Depends(get_field_attendance_filters)]


@router.post("", response_model=FieldAttendanceEventResponse, status_code=status.HTTP_201_CREATED)
async def create_field_attendance_event(
    data: FieldAttendanceEventCreate,
    service: FieldAttendanceEventServiceDep,
    request_context: CurrentRequestContext,
) -> FieldAttendanceEventResponse:
    try:
        event = await service.create(data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except SelfieFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Selfie file not found"
        ) from exc
    except FieldAttendanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return FieldAttendanceEventResponse.model_validate(event)


@router.get("", response_model=list[FieldAttendanceEventResponse])
async def list_field_attendance_events(
    service: FieldAttendanceEventServiceDep, request_context: CurrentRequestContext
) -> list[FieldAttendanceEventResponse]:
    events = await service.list(request_context)
    return [FieldAttendanceEventResponse.model_validate(item) for item in events]


@router.get("/paginated", response_model=Page[FieldAttendanceEventResponse])
async def list_field_attendance_events_paginated(
    service: FieldAttendanceEventServiceDep,
    pagination: Pagination,
    request_context: CurrentRequestContext,
    filters: FieldAttendanceFilters,
) -> Page[FieldAttendanceEventResponse]:
    page = await service.list_paginated(request_context, pagination, filters=filters)
    return Page(
        items=[FieldAttendanceEventResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{event_id}", response_model=FieldAttendanceEventResponse)
async def get_field_attendance_event(
    event_id: uuid.UUID,
    service: FieldAttendanceEventServiceDep,
    request_context: CurrentRequestContext,
) -> FieldAttendanceEventResponse:
    try:
        event = await service.get(event_id, request_context)
    except FieldAttendanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Field attendance event not found"
        )
    return FieldAttendanceEventResponse.model_validate(event)


@router.put("/{event_id}", response_model=FieldAttendanceEventResponse)
async def update_field_attendance_event(
    event_id: uuid.UUID,
    data: FieldAttendanceEventUpdate,
    service: FieldAttendanceEventServiceDep,
    request_context: CurrentRequestContext,
) -> FieldAttendanceEventResponse:
    try:
        event = await service.update(event_id, data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except SelfieFileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Selfie file not found"
        ) from exc
    except FieldAttendanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Field attendance event not found"
        )
    return FieldAttendanceEventResponse.model_validate(event)


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_field_attendance_event(
    event_id: uuid.UUID,
    service: FieldAttendanceEventServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(event_id, request_context)
    except FieldAttendanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Field attendance event not found"
        )
