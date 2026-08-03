import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.overtime_request import (
    OvertimeRequestCreate,
    OvertimeRequestResponse,
    OvertimeRequestUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.overtime_request import (
    EmployeeNotFoundError,
    InvalidOvertimeTimeRangeError,
    OvertimeRequestService,
)

router = APIRouter(prefix="/hr/overtime-requests", tags=["Overtime Requests"])


def get_overtime_request_service() -> OvertimeRequestService:
    return OvertimeRequestService()


OvertimeRequestServiceDep = Annotated[
    OvertimeRequestService, Depends(get_overtime_request_service)
]


def get_overtime_request_filters(
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`employee_id`, `status`), scoped to Overtime Requests."""
    values: dict[str, Any] = {}
    if employee_id is not None:
        values["employee_id"] = employee_id
    if status is not None:
        values["status"] = status
    return FilterParams(values=values)


OvertimeRequestFilters = Annotated[FilterParams, Depends(get_overtime_request_filters)]


@router.post("", response_model=OvertimeRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_overtime_request(
    data: OvertimeRequestCreate, service: OvertimeRequestServiceDep, _: CurrentUser
) -> OvertimeRequestResponse:
    try:
        overtime_request = await service.create(data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except InvalidOvertimeTimeRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_time must be after start_time",
        ) from exc
    return OvertimeRequestResponse.model_validate(overtime_request)


@router.get("", response_model=list[OvertimeRequestResponse])
async def list_overtime_requests(
    service: OvertimeRequestServiceDep, _: CurrentUser
) -> list[OvertimeRequestResponse]:
    overtime_requests = await service.list()
    return [OvertimeRequestResponse.model_validate(item) for item in overtime_requests]


@router.get("/paginated", response_model=Page[OvertimeRequestResponse])
async def list_overtime_requests_paginated(
    service: OvertimeRequestServiceDep,
    pagination: Pagination,
    search: Search,
    filters: OvertimeRequestFilters,
    _: CurrentUser,
) -> Page[OvertimeRequestResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[OvertimeRequestResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{overtime_request_id}", response_model=OvertimeRequestResponse)
async def get_overtime_request(
    overtime_request_id: uuid.UUID, service: OvertimeRequestServiceDep, _: CurrentUser
) -> OvertimeRequestResponse:
    overtime_request = await service.get(overtime_request_id)
    if overtime_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Overtime request not found"
        )
    return OvertimeRequestResponse.model_validate(overtime_request)


@router.put("/{overtime_request_id}", response_model=OvertimeRequestResponse)
async def update_overtime_request(
    overtime_request_id: uuid.UUID,
    data: OvertimeRequestUpdate,
    service: OvertimeRequestServiceDep,
    _: CurrentUser,
) -> OvertimeRequestResponse:
    try:
        overtime_request = await service.update(overtime_request_id, data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except InvalidOvertimeTimeRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_time must be after start_time",
        ) from exc
    if overtime_request is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Overtime request not found"
        )
    return OvertimeRequestResponse.model_validate(overtime_request)


@router.delete("/{overtime_request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_overtime_request(
    overtime_request_id: uuid.UUID, service: OvertimeRequestServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(overtime_request_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Overtime request not found"
        )
