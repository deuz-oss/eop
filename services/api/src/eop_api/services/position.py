import uuid
from collections.abc import Callable, Sequence

from eop_api.exceptions.department import DepartmentOrganizationMismatchError
from eop_api.models.position import Position
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.position import PositionCreate, PositionUpdate
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class OrganizationNotFoundError(Exception):
    """Raised when the organization referenced by a Position does not exist.

    Local to the Position module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class DepartmentNotFoundError(Exception):
    """Raised when the department referenced by a Position does not exist."""


class DuplicatePositionCodeError(Exception):
    """Raised when a position code is already used within its organization."""


class PositionService:
    """Business logic for `Position`. Owns the transaction boundary via a UoW.

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

    async def create(self, data: PositionCreate) -> Position:
        async with self._uow_factory() as uow:
            repo = PositionRepository(uow.session)
            org_repo = OrganizationRepository(uow.session)
            dept_repo = DepartmentRepository(uow.session)

            if not await org_repo.exists(data.organization_id):
                raise OrganizationNotFoundError(str(data.organization_id))

            department = await dept_repo.get(data.department_id)
            if department is None:
                raise DepartmentNotFoundError(str(data.department_id))
            if department.organization_id != data.organization_id:
                raise DepartmentOrganizationMismatchError(str(data.department_id))

            if await repo.get_by_organization_and_code(data.organization_id, data.code):
                raise DuplicatePositionCodeError(data.code)

            position = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(position)
            return position

    async def get(self, position_id: uuid.UUID) -> Position | None:
        async with self._uow_factory() as uow:
            repo = PositionRepository(uow.session)
            position = await repo.get(position_id)
            if position is not None:
                uow.session.expunge(position)
            return position

    async def list(self) -> Sequence[Position]:
        async with self._uow_factory() as uow:
            repo = PositionRepository(uow.session)
            positions = await repo.list()
            uow.session.expunge_all()
            return positions

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Position]:
        async with self._uow_factory() as uow:
            repo = PositionRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, position_id: uuid.UUID, data: PositionUpdate) -> Position | None:
        """Updates a Position, including (as an administrative operation) its
        `organization_id` and `department_id`.

        The *effective* department (whichever `department_id` the position will
        have once this update is applied -- whether it's part of this request or
        was already set) is always validated against the *effective*
        organization. This guarantees a position can never end up pointing at a
        department in a different organization, even when an update only
        changes `organization_id` and leaves `department_id` untouched.
        """
        async with self._uow_factory() as uow:
            repo = PositionRepository(uow.session)
            position = await repo.get(position_id)
            if position is None:
                return None

            values = data.model_dump(exclude_unset=True)

            organization_id = values.get("organization_id", position.organization_id)
            department_id = values.get("department_id", position.department_id)
            code = values.get("code", position.code)

            if "organization_id" in values:
                org_repo = OrganizationRepository(uow.session)
                if not await org_repo.exists(organization_id):
                    raise OrganizationNotFoundError(str(organization_id))

            dept_repo = DepartmentRepository(uow.session)
            department = await dept_repo.get(department_id)
            if department is None:
                raise DepartmentNotFoundError(str(department_id))
            if department.organization_id != organization_id:
                raise DepartmentOrganizationMismatchError(str(department_id))

            if "organization_id" in values or "code" in values:
                existing = await repo.get_by_organization_and_code(organization_id, code)
                if existing is not None and existing.id != position_id:
                    raise DuplicatePositionCodeError(code)

            updated = await repo.update(position_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, position_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = PositionRepository(uow.session)
            deleted = await repo.delete(position_id)
            if deleted:
                await uow.commit()
            return deleted
