import uuid
from collections.abc import Callable, Sequence

from eop_api.models.employee import Employee
from eop_api.repositories.employee import EmployeeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.employee import EmployeeCreate, EmployeeUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class OrganizationNotFoundError(Exception):
    """Raised when the organization referenced by an Employee does not exist.

    Local to the Employee module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class DuplicateEmployeeEmailError(Exception):
    """Raised when an employee email is already in use."""


class EmployeeService:
    """Business logic for `Employee`. Owns the transaction boundary via a UoW.

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

    async def create(self, data: EmployeeCreate) -> Employee:
        async with self._uow_factory() as uow:
            org_repo = OrganizationRepository(uow.session)
            if not await org_repo.exists(data.organization_id):
                raise OrganizationNotFoundError(str(data.organization_id))

            repo = EmployeeRepository(uow.session)
            if await repo.get_by_email(data.email):
                raise DuplicateEmployeeEmailError(data.email)

            employee = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(employee)
            return employee

    async def get(self, employee_id: uuid.UUID) -> Employee | None:
        async with self._uow_factory() as uow:
            repo = EmployeeRepository(uow.session)
            employee = await repo.get(employee_id)
            if employee is not None:
                uow.session.expunge(employee)
            return employee

    async def list(self) -> Sequence[Employee]:
        async with self._uow_factory() as uow:
            repo = EmployeeRepository(uow.session)
            employees = await repo.list()
            uow.session.expunge_all()
            return employees

    async def update(self, employee_id: uuid.UUID, data: EmployeeUpdate) -> Employee | None:
        async with self._uow_factory() as uow:
            repo = EmployeeRepository(uow.session)
            employee = await repo.get(employee_id)
            if employee is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "organization_id" in values:
                org_repo = OrganizationRepository(uow.session)
                if not await org_repo.exists(values["organization_id"]):
                    raise OrganizationNotFoundError(str(values["organization_id"]))

            if "email" in values:
                existing = await repo.get_by_email(values["email"])
                if existing is not None and existing.id != employee_id:
                    raise DuplicateEmployeeEmailError(values["email"])

            updated = await repo.update(employee_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, employee_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = EmployeeRepository(uow.session)
            deleted = await repo.delete(employee_id)
            if deleted:
                await uow.commit()
            return deleted
