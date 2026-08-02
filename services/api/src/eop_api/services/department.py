import uuid
from collections.abc import Callable, Sequence

from eop_api.models.department import Department
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.department import DepartmentCreate, DepartmentUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class OrganizationNotFoundError(Exception):
    """Raised when the organization referenced by a Department does not exist.

    Local to the Department module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class ParentDepartmentNotFoundError(Exception):
    """Raised when the parent referenced by a Department does not exist."""


class ParentOrganizationMismatchError(Exception):
    """Raised when a Department's parent belongs to a different organization."""


class SelfParentDepartmentError(Exception):
    """Raised when a Department's `parent_id` is set to its own id.

    Only a single-node cycle is rejected here -- full cycle detection across
    the tree is explicitly out of scope for this module.
    """


class DuplicateDepartmentCodeError(Exception):
    """Raised when a department code is already used within its organization."""


class DepartmentService:
    """Business logic for `Department`. Owns the transaction boundary via a UoW.

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

    async def create(self, data: DepartmentCreate) -> Department:
        async with self._uow_factory() as uow:
            repo = DepartmentRepository(uow.session)
            org_repo = OrganizationRepository(uow.session)

            if not await org_repo.exists(data.organization_id):
                raise OrganizationNotFoundError(str(data.organization_id))

            if data.parent_id is not None:
                parent = await repo.get(data.parent_id)
                if parent is None:
                    raise ParentDepartmentNotFoundError(str(data.parent_id))
                if parent.organization_id != data.organization_id:
                    raise ParentOrganizationMismatchError(str(data.parent_id))

            if await repo.get_by_organization_and_code(data.organization_id, data.code):
                raise DuplicateDepartmentCodeError(data.code)

            department = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(department)
            return department

    async def get(self, department_id: uuid.UUID) -> Department | None:
        async with self._uow_factory() as uow:
            repo = DepartmentRepository(uow.session)
            department = await repo.get(department_id)
            if department is not None:
                uow.session.expunge(department)
            return department

    async def list(self) -> Sequence[Department]:
        async with self._uow_factory() as uow:
            repo = DepartmentRepository(uow.session)
            departments = await repo.list()
            uow.session.expunge_all()
            return departments

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Department]:
        async with self._uow_factory() as uow:
            repo = DepartmentRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, department_id: uuid.UUID, data: DepartmentUpdate) -> Department | None:
        """Updates a Department, including (as an administrative operation) its
        `organization_id`.

        The *effective* parent (whichever `parent_id` the department will have
        once this update is applied -- whether it's part of this request or was
        already set) is always validated against the *effective* organization.
        This guarantees a department can never end up pointing at a parent in a
        different organization, even when an update only changes `organization_id`
        and leaves `parent_id` untouched.

        Reassigning `organization_id` never touches other rows: children keep
        their existing `organization_id`/`parent_id` and are not moved, cascaded,
        or otherwise recursively updated -- so moving a department can leave its
        *children* pointing at a now-mismatched organization. Callers who
        reassign a department to a new organization are responsible for
        reconciling its children themselves.
        """
        async with self._uow_factory() as uow:
            repo = DepartmentRepository(uow.session)
            department = await repo.get(department_id)
            if department is None:
                return None

            values = data.model_dump(exclude_unset=True)

            organization_id = values.get("organization_id", department.organization_id)
            code = values.get("code", department.code)
            parent_id = values.get("parent_id", department.parent_id)

            if parent_id == department_id:
                raise SelfParentDepartmentError(str(department_id))

            if "organization_id" in values:
                org_repo = OrganizationRepository(uow.session)
                if not await org_repo.exists(organization_id):
                    raise OrganizationNotFoundError(str(organization_id))

            if parent_id is not None:
                parent = await repo.get(parent_id)
                if parent is None:
                    raise ParentDepartmentNotFoundError(str(parent_id))
                if parent.organization_id != organization_id:
                    raise ParentOrganizationMismatchError(str(parent_id))

            if "organization_id" in values or "code" in values:
                existing = await repo.get_by_organization_and_code(organization_id, code)
                if existing is not None and existing.id != department_id:
                    raise DuplicateDepartmentCodeError(code)

            updated = await repo.update(department_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, department_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = DepartmentRepository(uow.session)
            deleted = await repo.delete(department_id)
            if deleted:
                await uow.commit()
            return deleted
