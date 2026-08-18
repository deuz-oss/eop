import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.foundation.monetary.types import InvalidMoneyError
from eop_api.schemas.allowance import AllowanceCreate, AllowanceResponse, AllowanceUpdate
from eop_api.schemas.pagination import Page
from eop_api.services.allowance import (
    AllowanceAuthorizationDeniedError,
    AllowanceDeletionNotAllowedError,
    AllowanceService,
    CorrectionTargetEmployeeMismatchError,
    CorrectionTargetNotFoundError,
    EmployeeNotFoundError,
    OverlappingAllowancePeriodError,
)

router = APIRouter(prefix="/hr/allowances", tags=["Allowances"])


def get_allowance_service() -> AllowanceService:
    return AllowanceService()


AllowanceServiceDep = Annotated[AllowanceService, Depends(get_allowance_service)]


@router.post("", response_model=AllowanceResponse, status_code=status.HTTP_201_CREATED)
async def create_allowance(
    data: AllowanceCreate,
    service: AllowanceServiceDep,
    request_context: CurrentRequestContext,
) -> AllowanceResponse:
    try:
        allowance = await service.create(data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except CorrectionTargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Correction target Allowance not found"
        ) from exc
    except CorrectionTargetEmployeeMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Correction target must belong to the same employee",
        ) from exc
    except OverlappingAllowancePeriodError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InvalidMoneyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except AllowanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return AllowanceResponse.model_validate(allowance)


@router.get("", response_model=list[AllowanceResponse])
async def list_allowances(
    service: AllowanceServiceDep, request_context: CurrentRequestContext
) -> list[AllowanceResponse]:
    allowances = await service.list(request_context)
    return [AllowanceResponse.model_validate(item) for item in allowances]


@router.get("/paginated", response_model=Page[AllowanceResponse])
async def list_allowances_paginated(
    service: AllowanceServiceDep,
    pagination: Pagination,
    search: Search,
    request_context: CurrentRequestContext,
) -> Page[AllowanceResponse]:
    page = await service.list_paginated(request_context, pagination, search)
    return Page(
        items=[AllowanceResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/history", response_model=list[AllowanceResponse])
async def list_allowance_history(
    service: AllowanceServiceDep, request_context: CurrentRequestContext
) -> list[AllowanceResponse]:
    """Every historical Allowance row for the caller's own employee."""
    history = await service.list_history(request_context)
    return [AllowanceResponse.model_validate(item) for item in history]


@router.get("/{allowance_id}", response_model=AllowanceResponse)
async def get_allowance(
    allowance_id: uuid.UUID,
    service: AllowanceServiceDep,
    request_context: CurrentRequestContext,
) -> AllowanceResponse:
    try:
        allowance = await service.get(allowance_id, request_context)
    except AllowanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if allowance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allowance not found")
    return AllowanceResponse.model_validate(allowance)


@router.put("/{allowance_id}", response_model=AllowanceResponse)
async def update_allowance(
    allowance_id: uuid.UUID,
    data: AllowanceUpdate,
    service: AllowanceServiceDep,
    request_context: CurrentRequestContext,
) -> AllowanceResponse:
    try:
        allowance = await service.update(allowance_id, data, request_context)
    except AllowanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if allowance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allowance not found")
    return AllowanceResponse.model_validate(allowance)


@router.delete("/{allowance_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_allowance(
    allowance_id: uuid.UUID,
    service: AllowanceServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(allowance_id, request_context)
    except AllowanceAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except AllowanceDeletionNotAllowedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Allowance records cannot be deleted; use the correction operation instead",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allowance not found")
