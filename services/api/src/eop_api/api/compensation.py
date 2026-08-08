import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.foundation.monetary.types import InvalidMoneyError
from eop_api.schemas.compensation import (
    CompensationCreate,
    CompensationResponse,
    CompensationUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.compensation import (
    CompensationService,
    DuplicateCompensationError,
    EmployeeNotFoundError,
)

router = APIRouter(prefix="/hr/compensation", tags=["Compensation"])


def get_compensation_service() -> CompensationService:
    return CompensationService()


CompensationServiceDep = Annotated[CompensationService, Depends(get_compensation_service)]


@router.post("", response_model=CompensationResponse, status_code=status.HTTP_201_CREATED)
async def create_compensation(
    data: CompensationCreate, service: CompensationServiceDep, _: CurrentUser
) -> CompensationResponse:
    try:
        compensation = await service.create(data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except DuplicateCompensationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Compensation already exists for this employee",
        ) from exc
    except InvalidMoneyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return CompensationResponse.model_validate(compensation)


@router.get("", response_model=list[CompensationResponse])
async def list_compensation(
    service: CompensationServiceDep, _: CurrentUser
) -> list[CompensationResponse]:
    compensations = await service.list()
    return [CompensationResponse.model_validate(item) for item in compensations]


@router.get("/paginated", response_model=Page[CompensationResponse])
async def list_compensation_paginated(
    service: CompensationServiceDep,
    pagination: Pagination,
    search: Search,
    _: CurrentUser,
) -> Page[CompensationResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[CompensationResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/by-employee/{employee_id}", response_model=CompensationResponse)
async def get_compensation_by_employee(
    employee_id: uuid.UUID, service: CompensationServiceDep, _: CurrentUser
) -> CompensationResponse:
    compensation = await service.get_by_employee(employee_id)
    if compensation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compensation not found"
        )
    return CompensationResponse.model_validate(compensation)


@router.get("/{compensation_id}", response_model=CompensationResponse)
async def get_compensation(
    compensation_id: uuid.UUID, service: CompensationServiceDep, _: CurrentUser
) -> CompensationResponse:
    compensation = await service.get(compensation_id)
    if compensation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compensation not found"
        )
    return CompensationResponse.model_validate(compensation)


@router.put("/{compensation_id}", response_model=CompensationResponse)
async def update_compensation(
    compensation_id: uuid.UUID,
    data: CompensationUpdate,
    service: CompensationServiceDep,
    _: CurrentUser,
) -> CompensationResponse:
    try:
        compensation = await service.update(compensation_id, data)
    except InvalidMoneyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    if compensation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compensation not found"
        )
    return CompensationResponse.model_validate(compensation)


@router.delete("/{compensation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_compensation(
    compensation_id: uuid.UUID, service: CompensationServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(compensation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Compensation not found"
        )
