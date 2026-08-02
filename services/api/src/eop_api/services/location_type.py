import uuid
from collections.abc import Callable, Sequence

from eop_api.models.location_type import LocationType
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.schemas.location_type import LocationTypeCreate, LocationTypeUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class LocationTypeService:
    """Business logic for `LocationType`. Owns the transaction boundary via a UoW.

    Returned entities are expunged from the unit-of-work's session before it
    closes: the UoW always rolls back (and thus expires all attributes) on
    exit, so callers holding on to the entity after this method returns would
    otherwise hit a `DetachedInstanceError` on first attribute access.

    `update` additionally refreshes the entity before expunging it: `updated_at`
    is a server-side `onupdate`, and SQLAlchemy does not eagerly fetch it back
    via RETURNING after a plain UPDATE flush the way it does for INSERT, so it
    would otherwise be left expired -- refreshing while still attached avoids a
    `MissingGreenlet` (the ORM's lazy-load-on-attribute-access is not awaitable
    once the session has exited its async context).
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: LocationTypeCreate) -> LocationType:
        async with self._uow_factory() as uow:
            repo = LocationTypeRepository(uow.session)
            location_type = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(location_type)
            return location_type

    async def get(self, location_type_id: uuid.UUID) -> LocationType | None:
        async with self._uow_factory() as uow:
            repo = LocationTypeRepository(uow.session)
            location_type = await repo.get(location_type_id)
            if location_type is not None:
                uow.session.expunge(location_type)
            return location_type

    async def list(self) -> Sequence[LocationType]:
        async with self._uow_factory() as uow:
            repo = LocationTypeRepository(uow.session)
            location_types = await repo.list()
            uow.session.expunge_all()
            return location_types

    async def list_paginated(
        self, pagination: PaginationParams, search: SearchParams | None = None
    ) -> Page[LocationType]:
        async with self._uow_factory() as uow:
            repo = LocationTypeRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, location_type_id: uuid.UUID, data: LocationTypeUpdate
    ) -> LocationType | None:
        async with self._uow_factory() as uow:
            repo = LocationTypeRepository(uow.session)
            location_type = await repo.update(
                location_type_id, **data.model_dump(exclude_unset=True)
            )
            if location_type is None:
                return None
            await uow.commit()
            await uow.session.refresh(location_type)
            uow.session.expunge(location_type)
            return location_type

    async def delete(self, location_type_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = LocationTypeRepository(uow.session)
            deleted = await repo.delete(location_type_id)
            if deleted:
                await uow.commit()
            return deleted
