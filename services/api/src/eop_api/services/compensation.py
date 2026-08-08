import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.foundation.monetary.types import Money
from eop_api.models.compensation import Compensation
from eop_api.repositories.compensation import CompensationRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.schemas.compensation import CompensationCreate, CompensationUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.compensation_authorization import CompensationAuthorizationEvaluator
from eop_api.services.employee_context import RequestContext
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Compensation does not exist."""


class DuplicateCompensationError(Exception):
    """Raised when a Compensation already exists for the given employee.

    Enforces "one active Compensation per Employee" at the service layer,
    in addition to the database's own unique constraint on `employee_id`.
    """


class CompensationAuthorizationDeniedError(Exception):
    """Raised when the Compensation Authorization Policy (Owner Only,
    `docs/architecture/capabilities/compensation/decision.md` §12 Addendum)
    denies a create/get/update/delete call -- i.e. `AuthorizationDecision.allowed`
    is `False`.

    Thrown only by `CompensationService`, never by
    `CompensationAuthorizationEvaluator` or `AuthorizationService` themselves.
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

    Every `create`/`get`/`update`/`delete` call is gated by the Compensation
    Authorization Policy (Owner Only): authorization is delegated to
    `AuthorizationService`/`CompensationAuthorizationEvaluator` via `_authorize`,
    and a denied decision raises `CompensationAuthorizationDeniedError`. This
    service never evaluates the policy itself -- see `_authorize`. `list`/
    `list_paginated` are scoped to the caller's own `employee_id` rather than
    authorized per-item, mirroring `AttendanceEventService`.

    `get_by_employee`'s `request_context` is optional: `PayrollCalculationService`
    calls it internally (not on behalf of a specific authenticated request) to
    read an arbitrary employee's active Compensation while computing payroll,
    the same way `ApprovalService`/`ReconciliationService` operate outside
    per-request authorization scope elsewhere in this repository. When
    `request_context` is omitted, no authorization check runs. Every API-router
    call site supplies it, so the Owner Only policy is enforced end-to-end for
    actual user requests.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(
        self, data: CompensationCreate, request_context: RequestContext
    ) -> Compensation:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if await repo.get_by_employee_id(data.employee_id) is not None:
                raise DuplicateCompensationError(str(data.employee_id))

            await self._authorize(data, request_context)

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

    async def get(
        self, compensation_id: uuid.UUID, request_context: RequestContext
    ) -> Compensation | None:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get(compensation_id)
            if compensation is None:
                return None
            await self._authorize(compensation, request_context)
            uow.session.expunge(compensation)
            return compensation

    async def get_by_employee(
        self, employee_id: uuid.UUID, request_context: RequestContext | None = None
    ) -> Compensation | None:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get_by_employee_id(employee_id)
            if compensation is None:
                return None
            if request_context is not None:
                await self._authorize(compensation, request_context)
            uow.session.expunge(compensation)
            return compensation

    async def list_active(self) -> Sequence[Compensation]:
        """Every `Compensation` row with `is_active=True`, unscoped.

        Used only by `PayrollCalculationService`'s internal batch
        orchestration, not reachable via any API route -- mirrors
        `get_by_employee`'s trusted-internal-caller pattern (no
        `request_context`, no authorization), for the same reason: this is a
        system-driven payroll computation step, not a request acting on
        behalf of one employee.
        """
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensations = await repo.list_active()
            uow.session.expunge_all()
            return compensations

    async def list(self, request_context: RequestContext) -> Sequence[Compensation]:
        """Compensation records owned by the caller's own `employee_id`."""
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensations = await repo.list()
            current_employee_id = request_context.employee_context.employee.id
            owned = [c for c in compensations if c.employee_id == current_employee_id]
            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self,
        request_context: RequestContext,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Compensation]:
        """Compensation records owned by the caller's own `employee_id`, paginated.

        `employee_id` is forced to the caller's own resolved employee id via
        repository-level filtering, overriding any client-supplied value in
        `filters` -- the caller cannot widen the scope by passing a different
        `employee_id`. Mirrors `AttendanceEventService.list_paginated`.
        """
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            scoped_values = dict(filters.values) if filters else {}
            scoped_values["employee_id"] = request_context.employee_context.employee.id
            scoped_filters = FilterParams(values=scoped_values)
            page = await repo.paginate(
                offset=pagination.offset,
                limit=pagination.limit,
                search=search,
                filters=scoped_filters,
            )
            uow.session.expunge_all()
            return page

    async def update(
        self,
        compensation_id: uuid.UUID,
        data: CompensationUpdate,
        request_context: RequestContext,
    ) -> Compensation | None:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get(compensation_id)
            if compensation is None:
                return None

            await self._authorize(compensation, request_context)

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

    async def delete(self, compensation_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get(compensation_id)
            if compensation is None:
                return False

            await self._authorize(compensation, request_context)

            deleted = await repo.delete(compensation_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Compensation Authorization Policy (Owner Only) for `resource`.

        `resource` is the `CompensationCreate` payload for `create`, or the
        already-loaded `Compensation` for `get`/`get_by_employee`/`update`/
        `delete`. This method only delegates to `AuthorizationService`/
        `CompensationAuthorizationEvaluator`; it contains no comparison of its
        own, so `CompensationService` never evaluates authorization itself.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(CompensationAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise CompensationAuthorizationDeniedError(
                decision.reason or "Compensation authorization denied"
            )
