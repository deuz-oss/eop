import uuid
from collections.abc import Callable, Sequence

from eop_api.models.location import Location
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.schemas.location import LocationCreate, LocationUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class ParentLocationNotFoundError(Exception):
    """Raised when the parent referenced by a Location does not exist.

    Local to the Location module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class SelfParentLocationError(Exception):
    """Raised when a Location's `parent_id` is set to its own id."""


class CyclicParentLocationError(Exception):
    """Raised when a Location's proposed `parent_id` is already a
    descendant of the Location being updated -- a multi-hop cycle
    (e.g. A -> B -> A) rather than the single-node case
    `SelfParentLocationError` covers.
    """


class LocationTypeNotFoundError(Exception):
    """Raised when the location type referenced by a Location does not exist."""


class DuplicateLocationCodeError(Exception):
    """Raised when a location code is already in use."""


class LocationService:
    """Business logic for `Location`. Owns the transaction boundary via a UoW.

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

    async def create(self, data: LocationCreate) -> Location:
        async with self._uow_factory() as uow:
            repo = LocationRepository(uow.session)

            type_repo = LocationTypeRepository(uow.session)
            if not await type_repo.exists(data.location_type_id):
                raise LocationTypeNotFoundError(str(data.location_type_id))

            if data.parent_id is not None and not await repo.exists(data.parent_id):
                raise ParentLocationNotFoundError(str(data.parent_id))

            if await repo.get_by_code(data.code) is not None:
                raise DuplicateLocationCodeError(data.code)

            location = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(location)
            return location

    async def get(self, location_id: uuid.UUID) -> Location | None:
        async with self._uow_factory() as uow:
            repo = LocationRepository(uow.session)
            location = await repo.get(location_id)
            if location is not None:
                uow.session.expunge(location)
            return location

    async def list(self) -> Sequence[Location]:
        async with self._uow_factory() as uow:
            repo = LocationRepository(uow.session)
            locations = await repo.list()
            uow.session.expunge_all()
            return locations

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Location]:
        async with self._uow_factory() as uow:
            repo = LocationRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, location_id: uuid.UUID, data: LocationUpdate) -> Location | None:
        async with self._uow_factory() as uow:
            repo = LocationRepository(uow.session)
            location = await repo.get(location_id)
            if location is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if values.get("parent_id") == location_id:
                raise SelfParentLocationError(str(location_id))

            if values.get("parent_id") is not None and not await repo.exists(values["parent_id"]):
                raise ParentLocationNotFoundError(str(values["parent_id"]))

            if values.get("parent_id") is not None and await self._would_create_cycle(
                repo, location_id, values["parent_id"]
            ):
                raise CyclicParentLocationError(str(values["parent_id"]))

            if "location_type_id" in values:
                type_repo = LocationTypeRepository(uow.session)
                if not await type_repo.exists(values["location_type_id"]):
                    raise LocationTypeNotFoundError(str(values["location_type_id"]))

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != location_id:
                    raise DuplicateLocationCodeError(values["code"])

            updated = await repo.update(location_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, location_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = LocationRepository(uow.session)
            deleted = await repo.delete(location_id)
            if deleted:
                await uow.commit()
            return deleted

    @staticmethod
    async def _would_create_cycle(
        repo: LocationRepository, location_id: uuid.UUID, proposed_parent_id: uuid.UUID
    ) -> bool:
        """Whether assigning `proposed_parent_id` as `location_id`'s parent
        would create a multi-hop cycle -- i.e. whether `location_id` is
        already an ancestor of `proposed_parent_id`.

        Walks up from `proposed_parent_id` via `parent_id` one hop at a time.
        `visited` guards against looping forever should the tree already
        contain a cycle from data predating this check.
        """
        visited: set[uuid.UUID] = set()
        current_id: uuid.UUID | None = proposed_parent_id
        while current_id is not None:
            if current_id == location_id:
                return True
            if current_id in visited:
                return False
            visited.add(current_id)
            current = await repo.get(current_id)
            current_id = current.parent_id if current is not None else None
        return False
