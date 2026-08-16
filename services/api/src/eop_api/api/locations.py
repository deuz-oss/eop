import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.location import LocationCreate, LocationResponse, LocationUpdate
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.location import (
    CyclicParentLocationError,
    DuplicateLocationCodeError,
    LocationService,
    LocationTypeNotFoundError,
    ParentLocationNotFoundError,
    SelfParentLocationError,
)

router = APIRouter(prefix="/locations", tags=["Locations"])


def get_location_service() -> LocationService:
    return LocationService()


LocationServiceDep = Annotated[LocationService, Depends(get_location_service)]

# Location Authorization Policy: reads remain open to any authenticated user
# (unchanged); create/update/delete require the "admin" role
# (`RequireRole("admin")`), the same mechanism `roles.py`/`stores.py` use --
# no new authorization framework introduced.
RequireLocationAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


def get_location_filters(
    location_type_id: Annotated[uuid.UUID | None, Query()] = None,
) -> FilterParams:
    """Shared equality filter (`location_type_id`), scoped to Locations."""
    return FilterParams(values={"location_type_id": location_type_id} if location_type_id else {})


LocationFilters = Annotated[FilterParams, Depends(get_location_filters)]


@router.post("", response_model=LocationResponse, status_code=status.HTTP_201_CREATED)
async def create_location(
    data: LocationCreate, service: LocationServiceDep, _: RequireLocationAdmin
) -> LocationResponse:
    try:
        location = await service.create(data)
    except LocationTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Location type not found"
        ) from exc
    except ParentLocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parent location not found"
        ) from exc
    except DuplicateLocationCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Location code already exists"
        ) from exc
    return LocationResponse.model_validate(location)


@router.get("", response_model=list[LocationResponse])
async def list_locations(service: LocationServiceDep, _: CurrentUser) -> list[LocationResponse]:
    locations = await service.list()
    return [LocationResponse.model_validate(location) for location in locations]


@router.get("/paginated", response_model=Page[LocationResponse])
async def list_locations_paginated(
    service: LocationServiceDep,
    pagination: Pagination,
    search: Search,
    filters: LocationFilters,
    _: CurrentUser,
) -> Page[LocationResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[LocationResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{location_id}", response_model=LocationResponse)
async def get_location(
    location_id: uuid.UUID, service: LocationServiceDep, _: CurrentUser
) -> LocationResponse:
    location = await service.get(location_id)
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return LocationResponse.model_validate(location)


@router.put("/{location_id}", response_model=LocationResponse)
async def update_location(
    location_id: uuid.UUID,
    data: LocationUpdate,
    service: LocationServiceDep,
    _: RequireLocationAdmin,
) -> LocationResponse:
    try:
        location = await service.update(location_id, data)
    except SelfParentLocationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A location cannot be its own parent",
        ) from exc
    except LocationTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Location type not found"
        ) from exc
    except ParentLocationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parent location not found"
        ) from exc
    except CyclicParentLocationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A location cannot be assigned a descendant as its parent",
        ) from exc
    except DuplicateLocationCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Location code already exists"
        ) from exc
    if location is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
    return LocationResponse.model_validate(location)


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: uuid.UUID, service: LocationServiceDep, _: RequireLocationAdmin
) -> None:
    deleted = await service.delete(location_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Location not found")
