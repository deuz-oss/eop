import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.store import StoreCreate, StoreResponse, StoreUpdate
from eop_api.services.store import (
    DuplicateStoreCodeError,
    OrganizationNotFoundError,
    StoreService,
    StoreTypeNotFoundError,
)

router = APIRouter(prefix="/stores", tags=["Store"])


def get_store_service() -> StoreService:
    return StoreService()


StoreServiceDep = Annotated[StoreService, Depends(get_store_service)]

# Store Authorization Policy: Role Based (`RequireRole("admin")`) -- `Store`
# has no natural owner-employee field, the same structural reason
# `JobRequisition`/`PayrollRun` use this mechanism. Reuses the same "admin"
# role/mechanism, no new authorization framework introduced.
RequireStoreAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
async def create_store(
    data: StoreCreate, service: StoreServiceDep, _: RequireStoreAdmin
) -> StoreResponse:
    try:
        store = await service.create(data)
    except DuplicateStoreCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Store code already exists"
        ) from exc
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except StoreTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Store type not found"
        ) from exc
    return StoreResponse.model_validate(store)


@router.get("", response_model=list[StoreResponse])
async def list_stores(service: StoreServiceDep, _: RequireStoreAdmin) -> list[StoreResponse]:
    stores = await service.list()
    return [StoreResponse.model_validate(item) for item in stores]


@router.get("/paginated", response_model=Page[StoreResponse])
async def list_stores_paginated(
    service: StoreServiceDep, pagination: Pagination, search: Search, _: RequireStoreAdmin
) -> Page[StoreResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[StoreResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{store_id}", response_model=StoreResponse)
async def get_store(
    store_id: uuid.UUID, service: StoreServiceDep, _: RequireStoreAdmin
) -> StoreResponse:
    store = await service.get(store_id)
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return StoreResponse.model_validate(store)


@router.put("/{store_id}", response_model=StoreResponse)
async def update_store(
    store_id: uuid.UUID, data: StoreUpdate, service: StoreServiceDep, _: RequireStoreAdmin
) -> StoreResponse:
    try:
        store = await service.update(store_id, data)
    except DuplicateStoreCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Store code already exists"
        ) from exc
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except StoreTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Store type not found"
        ) from exc
    if store is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
    return StoreResponse.model_validate(store)


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store(store_id: uuid.UUID, service: StoreServiceDep, _: RequireStoreAdmin) -> None:
    deleted = await service.delete(store_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")
