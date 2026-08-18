import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.leave_request import (
    LeaveRequestCreate,
    LeaveRequestRejectRequest,
    LeaveRequestResponse,
    LeaveRequestUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.approval import (
    AmbiguousLeaveBalanceError,
    ApprovalAuthorizationDeniedError,
    ApprovalService,
    CrossYearLeaveRequestError,
    InvalidApprovalStateError,
    LeaveBalanceNotFoundError,
    NegativeLeaveBalanceError,
    OverlappingLeaveRequestError,
)
from eop_api.services.leave_request import (
    EmployeeNotFoundError,
    InvalidLeaveDateRangeError,
    InvalidLeaveRequestStateError,
    LeaveAuthorizationDeniedError,
    LeaveRequestService,
)

router = APIRouter(prefix="/hr/leave-requests", tags=["Leave Requests"])


def get_leave_request_service() -> LeaveRequestService:
    return LeaveRequestService()


LeaveRequestServiceDep = Annotated[LeaveRequestService, Depends(get_leave_request_service)]


def get_approval_service() -> ApprovalService:
    return ApprovalService()


ApprovalServiceDep = Annotated[ApprovalService, Depends(get_approval_service)]


def get_leave_request_filters(
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`employee_id`, `status`), scoped to Leave Requests."""
    values: dict[str, Any] = {}
    if employee_id is not None:
        values["employee_id"] = employee_id
    if status is not None:
        values["status"] = status
    return FilterParams(values=values)


LeaveRequestFilters = Annotated[FilterParams, Depends(get_leave_request_filters)]


@router.post("", response_model=LeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    data: LeaveRequestCreate,
    service: LeaveRequestServiceDep,
    request_context: CurrentRequestContext,
) -> LeaveRequestResponse:
    try:
        leave_request = await service.create(data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except LeaveAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidLeaveDateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_date must not be before start_date",
        ) from exc
    return LeaveRequestResponse.model_validate(leave_request)


@router.get("", response_model=list[LeaveRequestResponse])
async def list_leave_requests(
    service: LeaveRequestServiceDep, request_context: CurrentRequestContext
) -> list[LeaveRequestResponse]:
    leave_requests = await service.list(request_context)
    return [LeaveRequestResponse.model_validate(item) for item in leave_requests]


@router.get("/paginated", response_model=Page[LeaveRequestResponse])
async def list_leave_requests_paginated(
    service: LeaveRequestServiceDep,
    pagination: Pagination,
    search: Search,
    filters: LeaveRequestFilters,
    request_context: CurrentRequestContext,
) -> Page[LeaveRequestResponse]:
    page = await service.list_paginated(request_context, pagination, search, filters)
    return Page(
        items=[LeaveRequestResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{leave_request_id}", response_model=LeaveRequestResponse)
async def get_leave_request(
    leave_request_id: uuid.UUID,
    service: LeaveRequestServiceDep,
    request_context: CurrentRequestContext,
) -> LeaveRequestResponse:
    try:
        leave_request = await service.get(leave_request_id, request_context)
    except LeaveAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if leave_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return LeaveRequestResponse.model_validate(leave_request)


@router.put("/{leave_request_id}", response_model=LeaveRequestResponse)
async def update_leave_request(
    leave_request_id: uuid.UUID,
    data: LeaveRequestUpdate,
    service: LeaveRequestServiceDep,
    request_context: CurrentRequestContext,
) -> LeaveRequestResponse:
    try:
        leave_request = await service.update(leave_request_id, data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except LeaveAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidLeaveDateRangeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="end_date must not be before start_date",
        ) from exc
    except InvalidLeaveRequestStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if leave_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return LeaveRequestResponse.model_validate(leave_request)


@router.delete("/{leave_request_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_leave_request(
    leave_request_id: uuid.UUID,
    service: LeaveRequestServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(leave_request_id, request_context)
    except LeaveAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidLeaveRequestStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")


@router.post("/{leave_request_id}/approve", response_model=LeaveRequestResponse)
async def approve_leave_request(
    leave_request_id: uuid.UUID,
    service: ApprovalServiceDep,
    request_context: CurrentRequestContext,
) -> LeaveRequestResponse:
    try:
        leave_request = await service.approve_leave_request(leave_request_id, request_context)
    except ApprovalAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidApprovalStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CrossYearLeaveRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Leave request must not span more than one calendar year",
        ) from exc
    except LeaveBalanceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="No leave balance found for this employee and period",
        ) from exc
    except AmbiguousLeaveBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Multiple leave balances found for this employee and period",
        ) from exc
    except OverlappingLeaveRequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An approved leave request already overlaps this date range",
        ) from exc
    except NegativeLeaveBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Approving this request would leave a negative leave balance",
        ) from exc
    if leave_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return LeaveRequestResponse.model_validate(leave_request)


@router.post("/{leave_request_id}/reject", response_model=LeaveRequestResponse)
async def reject_leave_request(
    leave_request_id: uuid.UUID,
    data: LeaveRequestRejectRequest,
    service: ApprovalServiceDep,
    request_context: CurrentRequestContext,
) -> LeaveRequestResponse:
    try:
        leave_request = await service.reject_leave_request(
            leave_request_id, request_context, data.reason
        )
    except ApprovalAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except InvalidApprovalStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if leave_request is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Leave request not found")
    return LeaveRequestResponse.model_validate(leave_request)
