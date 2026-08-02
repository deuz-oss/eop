import uuid
from collections.abc import Callable, Sequence

from eop_api.models.employment_status import EmploymentStatus
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.schemas.employment_status import EmploymentStatusCreate, EmploymentStatusUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateEmploymentStatusCodeError(Exception):
    """Raised when an employment status code is already in use."""


class EmploymentStatusService:
    """Business logic for `EmploymentStatus`. Owns the transaction boundary via a UoW.

    `EmploymentStatus` is global master data -- it does not belong to an
    Organization, Department, Team, Position, or Location, and has no
    hierarchy.

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

    async def create(self, data: EmploymentStatusCreate) -> EmploymentStatus:
        async with self._uow_factory() as uow:
            repo = EmploymentStatusRepository(uow.session)

            if await repo.get_by_code(data.code):
                raise DuplicateEmploymentStatusCodeError(data.code)

            employment_status = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(employment_status)
            return employment_status

    async def get(self, employment_status_id: uuid.UUID) -> EmploymentStatus | None:
        async with self._uow_factory() as uow:
            repo = EmploymentStatusRepository(uow.session)
            employment_status = await repo.get(employment_status_id)
            if employment_status is not None:
                uow.session.expunge(employment_status)
            return employment_status

    async def list(self) -> Sequence[EmploymentStatus]:
        async with self._uow_factory() as uow:
            repo = EmploymentStatusRepository(uow.session)
            employment_statuses = await repo.list()
            uow.session.expunge_all()
            return employment_statuses

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[EmploymentStatus]:
        async with self._uow_factory() as uow:
            repo = EmploymentStatusRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, employment_status_id: uuid.UUID, data: EmploymentStatusUpdate
    ) -> EmploymentStatus | None:
        async with self._uow_factory() as uow:
            repo = EmploymentStatusRepository(uow.session)
            employment_status = await repo.get(employment_status_id)
            if employment_status is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != employment_status_id:
                    raise DuplicateEmploymentStatusCodeError(values["code"])

            updated = await repo.update(employment_status_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, employment_status_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = EmploymentStatusRepository(uow.session)
            deleted = await repo.delete(employment_status_id)
            if deleted:
                await uow.commit()
            return deleted
