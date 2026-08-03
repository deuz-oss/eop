import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.shift import ShiftCreate, ShiftResponse, ShiftUpdate
from eop_api.services.shift import (
    DuplicateShiftCodeError,
    InvalidBreakDurationError,
    InvalidShiftTimeError,
    ShiftService,
)

router = APIRouter(prefix="/hr/shifts", tags=["Shifts"])


def get_shift_service() -> ShiftService:
    return ShiftService()


ShiftServiceDep = Annotated[ShiftService, Depends(get_shift_service)]


@router.post("", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
async def create_shift(
    data: ShiftCreate, service: ShiftServiceDep, _: CurrentUser
) -> ShiftResponse:
    try:
        shift = await service.create(data)
    except DuplicateShiftCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shift code already exists",
        ) from exc
    except InvalidShiftTimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Shift start_time and end_time must not be equal",
        ) from exc
    except InvalidBreakDurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Shift break_duration_minutes must not be negative",
        ) from exc
    return ShiftResponse.model_validate(shift)


@router.get("", response_model=list[ShiftResponse])
async def list_shifts(service: ShiftServiceDep, _: CurrentUser) -> list[ShiftResponse]:
    shifts = await service.list()
    return [ShiftResponse.model_validate(item) for item in shifts]


@router.get("/paginated", response_model=Page[ShiftResponse])
async def list_shifts_paginated(
    service: ShiftServiceDep,
    pagination: Pagination,
    search: Search,
    _: CurrentUser,
) -> Page[ShiftResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[ShiftResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{shift_id}", response_model=ShiftResponse)
async def get_shift(
    shift_id: uuid.UUID, service: ShiftServiceDep, _: CurrentUser
) -> ShiftResponse:
    shift = await service.get(shift_id)
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    return ShiftResponse.model_validate(shift)


@router.put("/{shift_id}", response_model=ShiftResponse)
async def update_shift(
    shift_id: uuid.UUID,
    data: ShiftUpdate,
    service: ShiftServiceDep,
    _: CurrentUser,
) -> ShiftResponse:
    try:
        shift = await service.update(shift_id, data)
    except DuplicateShiftCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Shift code already exists",
        ) from exc
    except InvalidShiftTimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Shift start_time and end_time must not be equal",
        ) from exc
    except InvalidBreakDurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Shift break_duration_minutes must not be negative",
        ) from exc
    if shift is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    return ShiftResponse.model_validate(shift)


@router.delete("/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(shift_id: uuid.UUID, service: ShiftServiceDep, _: CurrentUser) -> None:
    deleted = await service.delete(shift_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
