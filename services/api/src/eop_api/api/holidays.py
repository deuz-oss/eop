import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.holiday import HolidayCreate, HolidayResponse, HolidayUpdate
from eop_api.schemas.pagination import Page
from eop_api.services.holiday import (
    DuplicateHolidayCodeError,
    DuplicateHolidayDateError,
    HolidayService,
)

router = APIRouter(prefix="/hr/holidays", tags=["Holidays"])


def get_holiday_service() -> HolidayService:
    return HolidayService()


HolidayServiceDep = Annotated[HolidayService, Depends(get_holiday_service)]

# HR Master/Reference Data Authorization Policy: Role Based (`RequireRole("admin")`)
# for create/update/delete; reads remain open to any authenticated user.
# Reopened per CTO decision H2 (`HOLIDAY_CALENDAR_DESIGN.md` addendum) -- this
# family (`Holiday`, `Shift`, `JobGrade`, `EmploymentType`, `EmploymentStatus`)
# previously followed a deliberate `CurrentUser`-only precedent; the same
# `RequireRole("admin")` mechanism `Location`/`Store`/`PayrollRun` already use
# is reused here, no new authorization framework introduced.
RequireHrMasterDataAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=HolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_holiday(
    data: HolidayCreate, service: HolidayServiceDep, _: RequireHrMasterDataAdmin
) -> HolidayResponse:
    try:
        holiday = await service.create(data)
    except DuplicateHolidayCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holiday code already exists",
        ) from exc
    except DuplicateHolidayDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holiday date already exists",
        ) from exc
    return HolidayResponse.model_validate(holiday)


@router.get("", response_model=list[HolidayResponse])
async def list_holidays(service: HolidayServiceDep, _: CurrentUser) -> list[HolidayResponse]:
    holidays = await service.list()
    return [HolidayResponse.model_validate(item) for item in holidays]


@router.get("/paginated", response_model=Page[HolidayResponse])
async def list_holidays_paginated(
    service: HolidayServiceDep,
    pagination: Pagination,
    search: Search,
    _: CurrentUser,
) -> Page[HolidayResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[HolidayResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{holiday_id}", response_model=HolidayResponse)
async def get_holiday(
    holiday_id: uuid.UUID, service: HolidayServiceDep, _: CurrentUser
) -> HolidayResponse:
    holiday = await service.get(holiday_id)
    if holiday is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
    return HolidayResponse.model_validate(holiday)


@router.put("/{holiday_id}", response_model=HolidayResponse)
async def update_holiday(
    holiday_id: uuid.UUID,
    data: HolidayUpdate,
    service: HolidayServiceDep,
    _: RequireHrMasterDataAdmin,
) -> HolidayResponse:
    try:
        holiday = await service.update(holiday_id, data)
    except DuplicateHolidayCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holiday code already exists",
        ) from exc
    except DuplicateHolidayDateError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Holiday date already exists",
        ) from exc
    if holiday is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
    return HolidayResponse.model_validate(holiday)


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(
    holiday_id: uuid.UUID, service: HolidayServiceDep, _: RequireHrMasterDataAdmin
) -> None:
    deleted = await service.delete(holiday_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holiday not found")
