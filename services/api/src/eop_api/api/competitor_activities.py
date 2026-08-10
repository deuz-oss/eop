import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.schemas.competitor_activity import (
    CompetitorActivityCreate,
    CompetitorActivityResponse,
    CompetitorActivityUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.competitor_activity import (
    CompetitorActivityAuthorizationDeniedError,
    CompetitorActivityService,
    VisitNotFoundError,
)

router = APIRouter(prefix="/competitor-activities", tags=["Visit"])


def get_competitor_activity_service() -> CompetitorActivityService:
    return CompetitorActivityService()


CompetitorActivityServiceDep = Annotated[
    CompetitorActivityService, Depends(get_competitor_activity_service)
]


@router.post("", response_model=CompetitorActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_competitor_activity(
    data: CompetitorActivityCreate,
    service: CompetitorActivityServiceDep,
    request_context: CurrentRequestContext,
) -> CompetitorActivityResponse:
    try:
        activity = await service.create(data, request_context)
    except VisitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found"
        ) from exc
    except CompetitorActivityAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return CompetitorActivityResponse.model_validate(activity)


@router.get("", response_model=list[CompetitorActivityResponse])
async def list_competitor_activities(
    service: CompetitorActivityServiceDep, request_context: CurrentRequestContext
) -> list[CompetitorActivityResponse]:
    activities = await service.list(request_context)
    return [CompetitorActivityResponse.model_validate(item) for item in activities]


@router.get("/paginated", response_model=Page[CompetitorActivityResponse])
async def list_competitor_activities_paginated(
    service: CompetitorActivityServiceDep,
    pagination: Pagination,
    request_context: CurrentRequestContext,
) -> Page[CompetitorActivityResponse]:
    page = await service.list_paginated(request_context, pagination)
    return Page(
        items=[CompetitorActivityResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/by-visit/{visit_id}", response_model=list[CompetitorActivityResponse])
async def list_competitor_activities_by_visit(
    visit_id: uuid.UUID,
    service: CompetitorActivityServiceDep,
    request_context: CurrentRequestContext,
) -> list[CompetitorActivityResponse]:
    try:
        activities = await service.list_by_visit_id(visit_id, request_context)
    except VisitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found"
        ) from exc
    except CompetitorActivityAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return [CompetitorActivityResponse.model_validate(item) for item in activities]


@router.get("/{activity_id}", response_model=CompetitorActivityResponse)
async def get_competitor_activity(
    activity_id: uuid.UUID,
    service: CompetitorActivityServiceDep,
    request_context: CurrentRequestContext,
) -> CompetitorActivityResponse:
    try:
        activity = await service.get(activity_id, request_context)
    except CompetitorActivityAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competitor activity not found"
        )
    return CompetitorActivityResponse.model_validate(activity)


@router.put("/{activity_id}", response_model=CompetitorActivityResponse)
async def update_competitor_activity(
    activity_id: uuid.UUID,
    data: CompetitorActivityUpdate,
    service: CompetitorActivityServiceDep,
    request_context: CurrentRequestContext,
) -> CompetitorActivityResponse:
    try:
        activity = await service.update(activity_id, data, request_context)
    except CompetitorActivityAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if activity is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competitor activity not found"
        )
    return CompetitorActivityResponse.model_validate(activity)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_competitor_activity(
    activity_id: uuid.UUID,
    service: CompetitorActivityServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(activity_id, request_context)
    except CompetitorActivityAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Competitor activity not found"
        )
