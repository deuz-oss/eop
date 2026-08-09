import uuid
from collections.abc import Callable, Sequence

from eop_api.models.store import Store
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.store import StoreRepository
from eop_api.repositories.store_type import StoreTypeRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.schemas.store import StoreCreate, StoreUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateStoreCodeError(Exception):
    """Raised when a store code is already in use."""


class OrganizationNotFoundError(Exception):
    """Raised when the organization referenced by a Store does not exist."""


class StoreTypeNotFoundError(Exception):
    """Raised when the store type referenced by a Store does not exist."""


class StoreService:
    """Business logic for `Store`. Owns the transaction boundary via a UoW.

    Mirrors `JobRequisitionService`'s structure exactly -- master-data-shaped
    CRUD, existence checks for both referenced aggregates, plain `code`
    uniqueness. No status/lifecycle, no authorization evaluator of its own
    (`RequireRole("admin")` at the API layer, per
    `docs/architecture/capabilities/store/
    iteration-1-scope-and-implementation-plan.md` §7 -- `Store` has no
    natural owner-employee field).

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: StoreCreate) -> Store:
        async with self._uow_factory() as uow:
            repo = StoreRepository(uow.session)

            if await repo.get_by_code(data.code) is not None:
                raise DuplicateStoreCodeError(data.code)

            if not await OrganizationRepository(uow.session).exists(data.organization_id):
                raise OrganizationNotFoundError(str(data.organization_id))

            if not await StoreTypeRepository(uow.session).exists(data.store_type_id):
                raise StoreTypeNotFoundError(str(data.store_type_id))

            store = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(store)
            return store

    async def get(self, store_id: uuid.UUID) -> Store | None:
        async with self._uow_factory() as uow:
            repo = StoreRepository(uow.session)
            store = await repo.get(store_id)
            if store is not None:
                uow.session.expunge(store)
            return store

    async def list(self) -> Sequence[Store]:
        async with self._uow_factory() as uow:
            repo = StoreRepository(uow.session)
            stores = await repo.list()
            uow.session.expunge_all()
            return stores

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Store]:
        async with self._uow_factory() as uow:
            repo = StoreRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, store_id: uuid.UUID, data: StoreUpdate) -> Store | None:
        async with self._uow_factory() as uow:
            repo = StoreRepository(uow.session)
            store = await repo.get(store_id)
            if store is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != store_id:
                    raise DuplicateStoreCodeError(values["code"])

            if "organization_id" in values and not await OrganizationRepository(uow.session).exists(
                values["organization_id"]
            ):
                raise OrganizationNotFoundError(str(values["organization_id"]))

            if "store_type_id" in values and not await StoreTypeRepository(uow.session).exists(
                values["store_type_id"]
            ):
                raise StoreTypeNotFoundError(str(values["store_type_id"]))

            updated = await repo.update(store_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, store_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = StoreRepository(uow.session)
            deleted = await repo.delete(store_id)
            if deleted:
                await uow.commit()
            return deleted
