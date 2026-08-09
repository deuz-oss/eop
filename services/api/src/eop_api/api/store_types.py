import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.store_type import StoreTypeCreate, StoreTypeResponse, StoreTypeUpdate
from eop_api.services.store_type import DuplicateStoreTypeCodeError, StoreTypeService

router = APIRouter(prefix="/store-types", tags=["Store"])


def get_store_type_service() -> StoreTypeService:
    return StoreTypeService()


StoreTypeServiceDep = Annotated[StoreTypeService, Depends(get_store_type_service)]

# Store Authorization Policy: Role Based (`RequireRole("admin")`) -- `StoreType`
# has no natural owner-employee field, the same structural reason `PayrollRun`/
# `JobRequisition` use this mechanism. Reuses the same "admin" role/mechanism,
# no new authorization framework introduced.
RequireStoreAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=StoreTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_store_type(
    data: StoreTypeCreate, service: StoreTypeServiceDep, _: RequireStoreAdmin
) -> StoreTypeResponse:
    try:
        store_type = await service.create(data)
    except DuplicateStoreTypeCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Store type code already exists"
        ) from exc
    return StoreTypeResponse.model_validate(store_type)


@router.get("", response_model=list[StoreTypeResponse])
async def list_store_types(
    service: StoreTypeServiceDep, _: RequireStoreAdmin
) -> list[StoreTypeResponse]:
    store_types = await service.list()
    return [StoreTypeResponse.model_validate(item) for item in store_types]


@router.get("/paginated", response_model=Page[StoreTypeResponse])
async def list_store_types_paginated(
    service: StoreTypeServiceDep, pagination: Pagination, search: Search, _: RequireStoreAdmin
) -> Page[StoreTypeResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[StoreTypeResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{store_type_id}", response_model=StoreTypeResponse)
async def get_store_type(
    store_type_id: uuid.UUID, service: StoreTypeServiceDep, _: RequireStoreAdmin
) -> StoreTypeResponse:
    store_type = await service.get(store_type_id)
    if store_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store type not found")
    return StoreTypeResponse.model_validate(store_type)


@router.put("/{store_type_id}", response_model=StoreTypeResponse)
async def update_store_type(
    store_type_id: uuid.UUID,
    data: StoreTypeUpdate,
    service: StoreTypeServiceDep,
    _: RequireStoreAdmin,
) -> StoreTypeResponse:
    try:
        store_type = await service.update(store_type_id, data)
    except DuplicateStoreTypeCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Store type code already exists"
        ) from exc
    if store_type is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store type not found")
    return StoreTypeResponse.model_validate(store_type)


@router.delete("/{store_type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store_type(
    store_type_id: uuid.UUID, service: StoreTypeServiceDep, _: RequireStoreAdmin
) -> None:
    deleted = await service.delete(store_type_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store type not found")
