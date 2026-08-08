import uuid
from collections.abc import Callable, Sequence

from eop_api.foundation.monetary.types import Money
from eop_api.models.compensation import Compensation
from eop_api.repositories.compensation import CompensationRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.schemas.compensation import CompensationCreate, CompensationUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Compensation does not exist."""


class DuplicateCompensationError(Exception):
    """Raised when a Compensation already exists for the given employee.

    Enforces "one active Compensation per Employee" at the service layer,
    in addition to the database's own unique constraint on `employee_id`.
    """


class CompensationService:
    """Business logic for `Compensation`. Owns the transaction boundary via a UoW.

    Iteration 1, frozen scope only: Base Salary, represented by `Money`, and
    an `effective_from` date. No allowance, bonus, deduction, salary
    component, approval workflow, or history/versioning mechanism -- an
    `update()` mutates the same row in place; there is no historical record
    of a prior value.

    `Money` has no persistence of its own: this service constructs and
    validates a `Money` value at the boundary (on both write and read), and
    persists/reads its two component columns
    (`base_salary_amount`/`base_salary_currency`) directly.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: CompensationCreate) -> Compensation:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if await repo.get_by_employee_id(data.employee_id) is not None:
                raise DuplicateCompensationError(str(data.employee_id))

            money = Money(data.base_salary_amount, data.base_salary_currency)

            compensation = await repo.create(
                employee_id=data.employee_id,
                base_salary_amount=money.amount,
                base_salary_currency=money.currency,
                effective_from=data.effective_from,
            )
            await uow.commit()
            uow.session.expunge(compensation)
            return compensation

    async def get(self, compensation_id: uuid.UUID) -> Compensation | None:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get(compensation_id)
            if compensation is not None:
                uow.session.expunge(compensation)
            return compensation

    async def get_by_employee(self, employee_id: uuid.UUID) -> Compensation | None:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get_by_employee_id(employee_id)
            if compensation is not None:
                uow.session.expunge(compensation)
            return compensation

    async def list(self) -> Sequence[Compensation]:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensations = await repo.list()
            uow.session.expunge_all()
            return compensations

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Compensation]:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, compensation_id: uuid.UUID, data: CompensationUpdate
    ) -> Compensation | None:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get(compensation_id)
            if compensation is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "base_salary_amount" in values or "base_salary_currency" in values:
                amount = values.get("base_salary_amount", compensation.base_salary_amount)
                currency = values.get("base_salary_currency", compensation.base_salary_currency)
                money = Money(amount, currency)
                values["base_salary_amount"] = money.amount
                values["base_salary_currency"] = money.currency

            updated = await repo.update(compensation_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, compensation_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            deleted = await repo.delete(compensation_id)
            if deleted:
                await uow.commit()
            return deleted
