import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.location_type import (
    LocationTypeCreate,
    LocationTypeResponse,
    LocationTypeUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.location_type import LocationTypeService

router = APIRouter(prefix="/location-types", tags=["Location Types"])


def get_location_type_service() -> LocationTypeService:
    return LocationTypeService()


LocationTypeServiceDep = Annotated[LocationTypeService, Depends(get_location_type_service)]

# Location Type Authorization Policy: reads remain open to any authenticated
# user (unchanged); create/update/delete require the "admin" role
# (`RequireRole("admin")`), the same mechanism `roles.py`/`stores.py` use --
# no new authorization framework introduced.
RequireLocationAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=LocationTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_location_type(
    data: LocationTypeCreate, service: LocationTypeServiceDep, _: RequireLocationAdmin
) -> LocationTypeResponse:
    location_type = await service.create(data)
    return LocationTypeResponse.model_validate(location_type)


@router.get("", response_model=list[LocationTypeResponse])
async def list_location_types(
    service: LocationTypeServiceDep, _: CurrentUser
) -> list[LocationTypeResponse]:
    location_types = await service.list()
    return [LocationTypeResponse.model_validate(item) for item in location_types]


@router.get("/paginated", response_model=Page[LocationTypeResponse])
async def list_location_types_paginated(
    service: LocationTypeServiceDep, pagination: Pagination, search: Search, _: CurrentUser
) -> Page[LocationTypeResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[LocationTypeResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{location_type_id}", response_model=LocationTypeResponse)
async def get_location_type(
    location_type_id: uuid.UUID, service: LocationTypeServiceDep, _: CurrentUser
) -> LocationTypeResponse:
    location_type = await service.get(location_type_id)
    if location_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location type not found")
    return LocationTypeResponse.model_validate(location_type)


@router.patch("/{location_type_id}", response_model=LocationTypeResponse)
async def update_location_type(
    location_type_id: uuid.UUID,
    data: LocationTypeUpdate,
    service: LocationTypeServiceDep,
    _: RequireLocationAdmin,
) -> LocationTypeResponse:
    location_type = await service.update(location_type_id, data)
    if location_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location type not found")
    return LocationTypeResponse.model_validate(location_type)


@router.delete("/{location_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location_type(
    location_type_id: uuid.UUID, service: LocationTypeServiceDep, _: RequireLocationAdmin
) -> None:
    deleted = await service.delete(location_type_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location type not found")
