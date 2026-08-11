import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.schemas.pagination import Page
from eop_api.schemas.visit_photo import VisitPhotoCreate, VisitPhotoResponse, VisitPhotoUpdate
from eop_api.services.visit_photo import (
    FileObjectNotFoundError,
    VisitNotFoundError,
    VisitPhotoAuthorizationDeniedError,
    VisitPhotoService,
)

router = APIRouter(prefix="/visit-photos", tags=["Visit"])


def get_visit_photo_service() -> VisitPhotoService:
    return VisitPhotoService()


VisitPhotoServiceDep = Annotated[VisitPhotoService, Depends(get_visit_photo_service)]


@router.post("", response_model=VisitPhotoResponse, status_code=status.HTTP_201_CREATED)
async def create_visit_photo(
    data: VisitPhotoCreate,
    service: VisitPhotoServiceDep,
    request_context: CurrentRequestContext,
) -> VisitPhotoResponse:
    try:
        photo = await service.create(data, request_context)
    except VisitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found"
        ) from exc
    except FileObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File object not found"
        ) from exc
    except VisitPhotoAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return VisitPhotoResponse.model_validate(photo)


@router.get("", response_model=list[VisitPhotoResponse])
async def list_visit_photos(
    service: VisitPhotoServiceDep, request_context: CurrentRequestContext
) -> list[VisitPhotoResponse]:
    photos = await service.list(request_context)
    return [VisitPhotoResponse.model_validate(item) for item in photos]


@router.get("/paginated", response_model=Page[VisitPhotoResponse])
async def list_visit_photos_paginated(
    service: VisitPhotoServiceDep,
    pagination: Pagination,
    request_context: CurrentRequestContext,
    visit_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[VisitPhotoResponse]:
    page = await service.list_paginated(request_context, pagination, visit_id=visit_id)
    return Page(
        items=[VisitPhotoResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{photo_id}", response_model=VisitPhotoResponse)
async def get_visit_photo(
    photo_id: uuid.UUID,
    service: VisitPhotoServiceDep,
    request_context: CurrentRequestContext,
) -> VisitPhotoResponse:
    try:
        photo = await service.get(photo_id, request_context)
    except VisitPhotoAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit photo not found")
    return VisitPhotoResponse.model_validate(photo)


@router.put("/{photo_id}", response_model=VisitPhotoResponse)
async def update_visit_photo(
    photo_id: uuid.UUID,
    data: VisitPhotoUpdate,
    service: VisitPhotoServiceDep,
    request_context: CurrentRequestContext,
) -> VisitPhotoResponse:
    try:
        photo = await service.update(photo_id, data, request_context)
    except FileObjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File object not found"
        ) from exc
    except VisitPhotoAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if photo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit photo not found")
    return VisitPhotoResponse.model_validate(photo)


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_visit_photo(
    photo_id: uuid.UUID,
    service: VisitPhotoServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(photo_id, request_context)
    except VisitPhotoAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit photo not found")
