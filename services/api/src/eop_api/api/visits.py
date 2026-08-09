import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.schemas.visit import VisitCreate, VisitResponse, VisitUpdate
from eop_api.services.visit import (
    EmployeeNotFoundError,
    StoreNotFoundError,
    VisitAuthorizationDeniedError,
    VisitService,
)

router = APIRouter(prefix="/visits", tags=["Visit"])


def get_visit_service() -> VisitService:
    return VisitService()


VisitServiceDep = Annotated[VisitService, Depends(get_visit_service)]


def get_visit_filters(
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    store_id: Annotated[uuid.UUID | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`employee_id`, `store_id`), scoped to Visits."""
    values: dict[str, Any] = {}
    if employee_id is not None:
        values["employee_id"] = employee_id
    if store_id is not None:
        values["store_id"] = store_id
    return FilterParams(values=values)


VisitFilters = Annotated[FilterParams, Depends(get_visit_filters)]


@router.post("", response_model=VisitResponse, status_code=status.HTTP_201_CREATED)
async def create_visit(
    data: VisitCreate,
    service: VisitServiceDep,
    request_context: CurrentRequestContext,
) -> VisitResponse:
    try:
        visit = await service.create(data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except StoreNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Store not found"
        ) from exc
    except VisitAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return VisitResponse.model_validate(visit)


@router.get("", response_model=list[VisitResponse])
async def list_visits(
    service: VisitServiceDep, request_context: CurrentRequestContext
) -> list[VisitResponse]:
    visits = await service.list(request_context)
    return [VisitResponse.model_validate(item) for item in visits]


@router.get("/paginated", response_model=Page[VisitResponse])
async def list_visits_paginated(
    service: VisitServiceDep,
    pagination: Pagination,
    search: Search,
    filters: VisitFilters,
    request_context: CurrentRequestContext,
) -> Page[VisitResponse]:
    page = await service.list_paginated(request_context, pagination, search, filters)
    return Page(
        items=[VisitResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{visit_id}", response_model=VisitResponse)
async def get_visit(
    visit_id: uuid.UUID,
    service: VisitServiceDep,
    request_context: CurrentRequestContext,
) -> VisitResponse:
    try:
        visit = await service.get(visit_id, request_context)
    except VisitAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
    return VisitResponse.model_validate(visit)


@router.put("/{visit_id}", response_model=VisitResponse)
async def update_visit(
    visit_id: uuid.UUID,
    data: VisitUpdate,
    service: VisitServiceDep,
    request_context: CurrentRequestContext,
) -> VisitResponse:
    try:
        visit = await service.update(visit_id, data, request_context)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except StoreNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Store not found"
        ) from exc
    except VisitAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
    return VisitResponse.model_validate(visit)


@router.delete("/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visit(
    visit_id: uuid.UUID,
    service: VisitServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(visit_id, request_context)
    except VisitAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
