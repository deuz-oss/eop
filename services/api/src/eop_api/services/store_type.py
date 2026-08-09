import uuid
from collections.abc import Callable, Sequence

from eop_api.models.store_type import StoreType
from eop_api.repositories.store_type import StoreTypeRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.schemas.store_type import StoreTypeCreate, StoreTypeUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateStoreTypeCodeError(Exception):
    """Raised when a store type code is already in use."""


class StoreTypeService:
    """Business logic for `StoreType`. Owns the transaction boundary via a UoW.

    Master-data-shaped CRUD, mirroring `LocationTypeService`'s structure,
    plus a `code` uniqueness check mirroring `JobRequisitionService`'s.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: StoreTypeCreate) -> StoreType:
        async with self._uow_factory() as uow:
            repo = StoreTypeRepository(uow.session)

            if await repo.get_by_code(data.code) is not None:
                raise DuplicateStoreTypeCodeError(data.code)

            store_type = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(store_type)
            return store_type

    async def get(self, store_type_id: uuid.UUID) -> StoreType | None:
        async with self._uow_factory() as uow:
            repo = StoreTypeRepository(uow.session)
            store_type = await repo.get(store_type_id)
            if store_type is not None:
                uow.session.expunge(store_type)
            return store_type

    async def list(self) -> Sequence[StoreType]:
        async with self._uow_factory() as uow:
            repo = StoreTypeRepository(uow.session)
            store_types = await repo.list()
            uow.session.expunge_all()
            return store_types

    async def list_paginated(
        self, pagination: PaginationParams, search: SearchParams | None = None
    ) -> Page[StoreType]:
        async with self._uow_factory() as uow:
            repo = StoreTypeRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search
            )
            uow.session.expunge_all()
            return page

    async def update(self, store_type_id: uuid.UUID, data: StoreTypeUpdate) -> StoreType | None:
        async with self._uow_factory() as uow:
            repo = StoreTypeRepository(uow.session)
            store_type = await repo.get(store_type_id)
            if store_type is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != store_type_id:
                    raise DuplicateStoreTypeCodeError(values["code"])

            updated = await repo.update(store_type_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, store_type_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = StoreTypeRepository(uow.session)
            deleted = await repo.delete(store_type_id)
            if deleted:
                await uow.commit()
            return deleted
