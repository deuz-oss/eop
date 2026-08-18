import uuid
from collections.abc import Callable, Sequence

from eop_api.models.leave_balance import LeaveBalance
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.leave_balance import LeaveBalanceRepository
from eop_api.schemas.leave_balance import LeaveBalanceCreate, LeaveBalanceUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a LeaveBalance does not exist."""


class InvalidLeaveBalanceError(Exception):
    """Raised when a LeaveBalance's day counts are negative."""


class LeaveBalanceService:
    """Business logic for `LeaveBalance`. Owns the transaction boundary via a UoW.

    `LeaveBalance` is a persisted allocation/usage snapshot for one employee
    and one `period_year` -- not a calculation, ledger, or accrual record.
    `used_days`/`remaining_days` are controlled fields: `ApprovalService.
    _sync_leave_balance` is their only writer (deduction on `LeaveRequest`
    approval); this service never accepts a client-supplied value for
    either (`LeaveBalanceCreate`/`LeaveBalanceUpdate` have no such fields).
    `create` always starts a new row at `used_days=0`,
    `remaining_days=allocated_days`; `update` treats `allocated_days` as
    plain admin/HR allocation data -- generic-CRUD-writable -- and, when
    present in the payload, recomputes `remaining_days` against the
    persisted `used_days` so `remaining_days = allocated_days - used_days`
    always holds after this call. `allocated_days` and the effective
    `used_days`/`remaining_days` are validated non-negative. Accrual,
    carry-forward, expiration, leave-eligibility gating, and
    duplicate-period prevention are all explicitly out of scope for this
    module and belong to future PRs.

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

    async def create(self, data: LeaveBalanceCreate) -> LeaveBalance:
        async with self._uow_factory() as uow:
            repo = LeaveBalanceRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            _validate_non_negative(data.allocated_days, 0, data.allocated_days)

            leave_balance = await repo.create(
                **data.model_dump(), used_days=0, remaining_days=data.allocated_days
            )
            await uow.commit()
            uow.session.expunge(leave_balance)
            return leave_balance

    async def get(self, leave_balance_id: uuid.UUID) -> LeaveBalance | None:
        async with self._uow_factory() as uow:
            repo = LeaveBalanceRepository(uow.session)
            leave_balance = await repo.get(leave_balance_id)
            if leave_balance is not None:
                uow.session.expunge(leave_balance)
            return leave_balance

    async def list(self) -> Sequence[LeaveBalance]:
        async with self._uow_factory() as uow:
            repo = LeaveBalanceRepository(uow.session)
            leave_balances = await repo.list()
            uow.session.expunge_all()
            return leave_balances

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[LeaveBalance]:
        async with self._uow_factory() as uow:
            repo = LeaveBalanceRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, leave_balance_id: uuid.UUID, data: LeaveBalanceUpdate
    ) -> LeaveBalance | None:
        async with self._uow_factory() as uow:
            repo = LeaveBalanceRepository(uow.session)
            leave_balance = await repo.get(leave_balance_id)
            if leave_balance is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            used_days = leave_balance.used_days

            if "allocated_days" in values:
                values["remaining_days"] = values["allocated_days"] - used_days

            allocated_days = values.get("allocated_days", leave_balance.allocated_days)
            remaining_days = values.get("remaining_days", leave_balance.remaining_days)

            _validate_non_negative(allocated_days, used_days, remaining_days)

            updated = await repo.update(leave_balance_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, leave_balance_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = LeaveBalanceRepository(uow.session)
            deleted = await repo.delete(leave_balance_id)
            if deleted:
                await uow.commit()
            return deleted


def _validate_non_negative(allocated_days: int, used_days: int, remaining_days: int) -> None:
    if allocated_days < 0:
        raise InvalidLeaveBalanceError(f"allocated_days {allocated_days} must be >= 0")
    if used_days < 0:
        raise InvalidLeaveBalanceError(f"used_days {used_days} must be >= 0")
    if remaining_days < 0:
        raise InvalidLeaveBalanceError(f"remaining_days {remaining_days} must be >= 0")
