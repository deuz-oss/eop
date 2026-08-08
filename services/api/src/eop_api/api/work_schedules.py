import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.work_schedule import (
    WorkScheduleCreate,
    WorkScheduleResponse,
    WorkScheduleUpdate,
)
from eop_api.services.effective_dating_evaluator import AmbiguousEffectiveStateError
from eop_api.services.work_schedule import (
    CorrectionTargetEmployeeMismatchError,
    CorrectionTargetNotFoundError,
    EmployeeNotFoundError,
    OverlappingWorkSchedulePeriodError,
    ShiftNotFoundError,
    WorkScheduleAuthorizationDeniedError,
    WorkScheduleService,
)

router = APIRouter(prefix="/hr/work-schedules", tags=["Work Schedule"])


def get_work_schedule_service() -> WorkScheduleService:
    return WorkScheduleService()


WorkScheduleServiceDep = Annotated[WorkScheduleService, Depends(get_work_schedule_service)]


@router.post("", response_model=WorkScheduleResponse, status_code=status.HTTP_201_CREATED)
async def create_work_schedule(
    data: WorkScheduleCreate,
    service: WorkScheduleServiceDep,
    request_context: CurrentRequestContext,
) -> WorkScheduleResponse:
    try:
        work_schedule = await service.create(data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except ShiftNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found"
        ) from exc
    except CorrectionTargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Correction target WorkSchedule not found"
        ) from exc
    except CorrectionTargetEmployeeMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Correction target must belong to the same employee",
        ) from exc
    except OverlappingWorkSchedulePeriodError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except WorkScheduleAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return WorkScheduleResponse.model_validate(work_schedule)


@router.get("", response_model=list[WorkScheduleResponse])
async def list_work_schedules(
    service: WorkScheduleServiceDep, request_context: CurrentRequestContext
) -> list[WorkScheduleResponse]:
    work_schedules = await service.list(request_context)
    return [WorkScheduleResponse.model_validate(item) for item in work_schedules]


@router.get("/paginated", response_model=Page[WorkScheduleResponse])
async def list_work_schedules_paginated(
    service: WorkScheduleServiceDep,
    pagination: Pagination,
    search: Search,
    request_context: CurrentRequestContext,
) -> Page[WorkScheduleResponse]:
    page = await service.list_paginated(request_context, pagination, search)
    return Page(
        items=[WorkScheduleResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/by-employee/{employee_id}", response_model=WorkScheduleResponse)
async def get_work_schedule_by_employee(
    employee_id: uuid.UUID,
    service: WorkScheduleServiceDep,
    request_context: CurrentRequestContext,
    as_of: date | None = None,
) -> WorkScheduleResponse:
    """The WorkSchedule effective for `employee_id` as of `as_of` (default: today)."""
    try:
        work_schedule = await service.get_by_employee(employee_id, request_context, as_of)
    except WorkScheduleAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AmbiguousEffectiveStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if work_schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work schedule not found")
    return WorkScheduleResponse.model_validate(work_schedule)


@router.get("/{work_schedule_id}", response_model=WorkScheduleResponse)
async def get_work_schedule(
    work_schedule_id: uuid.UUID,
    service: WorkScheduleServiceDep,
    request_context: CurrentRequestContext,
) -> WorkScheduleResponse:
    try:
        work_schedule = await service.get(work_schedule_id, request_context)
    except WorkScheduleAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if work_schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work schedule not found")
    return WorkScheduleResponse.model_validate(work_schedule)


@router.put("/{work_schedule_id}", response_model=WorkScheduleResponse)
async def update_work_schedule(
    work_schedule_id: uuid.UUID,
    data: WorkScheduleUpdate,
    service: WorkScheduleServiceDep,
    request_context: CurrentRequestContext,
) -> WorkScheduleResponse:
    try:
        work_schedule = await service.update(work_schedule_id, data, request_context)
    except WorkScheduleAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if work_schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work schedule not found")
    return WorkScheduleResponse.model_validate(work_schedule)


@router.delete("/{work_schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_work_schedule(
    work_schedule_id: uuid.UUID,
    service: WorkScheduleServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(work_schedule_id, request_context)
    except WorkScheduleAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Work schedule not found")
