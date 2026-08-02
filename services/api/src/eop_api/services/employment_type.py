import uuid
from collections.abc import Callable, Sequence

from eop_api.models.employment_type import EmploymentType
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.schemas.employment_type import EmploymentTypeCreate, EmploymentTypeUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateEmploymentTypeCodeError(Exception):
    """Raised when an employment type code is already in use."""


class EmploymentTypeService:
    """Business logic for `EmploymentType`. Owns the transaction boundary via a UoW.

    `EmploymentType` is global master data -- it does not belong to an
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

    async def create(self, data: EmploymentTypeCreate) -> EmploymentType:
        async with self._uow_factory() as uow:
            repo = EmploymentTypeRepository(uow.session)

            if await repo.get_by_code(data.code):
                raise DuplicateEmploymentTypeCodeError(data.code)

            employment_type = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(employment_type)
            return employment_type

    async def get(self, employment_type_id: uuid.UUID) -> EmploymentType | None:
        async with self._uow_factory() as uow:
            repo = EmploymentTypeRepository(uow.session)
            employment_type = await repo.get(employment_type_id)
            if employment_type is not None:
                uow.session.expunge(employment_type)
            return employment_type

    async def list(self) -> Sequence[EmploymentType]:
        async with self._uow_factory() as uow:
            repo = EmploymentTypeRepository(uow.session)
            employment_types = await repo.list()
            uow.session.expunge_all()
            return employment_types

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[EmploymentType]:
        async with self._uow_factory() as uow:
            repo = EmploymentTypeRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, employment_type_id: uuid.UUID, data: EmploymentTypeUpdate
    ) -> EmploymentType | None:
        async with self._uow_factory() as uow:
            repo = EmploymentTypeRepository(uow.session)
            employment_type = await repo.get(employment_type_id)
            if employment_type is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != employment_type_id:
                    raise DuplicateEmploymentTypeCodeError(values["code"])

            updated = await repo.update(employment_type_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, employment_type_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = EmploymentTypeRepository(uow.session)
            deleted = await repo.delete(employment_type_id)
            if deleted:
                await uow.commit()
            return deleted
