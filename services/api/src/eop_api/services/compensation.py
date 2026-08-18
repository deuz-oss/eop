import uuid
from collections.abc import Callable, Sequence
from datetime import date
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
from eop_api.services.effective_dating_evaluator import EffectiveDatingEvaluator
from eop_api.services.employee_context import RequestContext
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Compensation does not exist."""


class CorrectionTargetNotFoundError(Exception):
    """Raised when `CompensationCreate.corrects_id` does not reference an
    existing Compensation row."""


class CorrectionTargetEmployeeMismatchError(Exception):
    """Raised when `CompensationCreate.corrects_id` references a Compensation
    row belonging to a different employee than `CompensationCreate.employee_id`."""


class OverlappingCompensationPeriodError(Exception):
    """Raised when a new Compensation row's effective period overlaps an
    existing row for the same employee (`decision.md` §19, Option O1).

    A correction row (`corrects_id` set) is exempt from this check only
    against the exact row it corrects -- see
    `CompensationRepository.find_overlapping_periods`'s `exclude_id`.
    """


class CompensationAuthorizationDeniedError(Exception):
    """Raised when the Compensation Authorization Policy (Owner Only,
    `docs/architecture/capabilities/compensation/decision.md` §12 Addendum)
    denies a create/get/update/delete call -- i.e. `AuthorizationDecision.allowed`
    is `False`.

    Thrown only by `CompensationService`, never by
    `CompensationAuthorizationEvaluator` or `AuthorizationService` themselves.
    """


class CompensationDeletionNotAllowedError(Exception):
    """Raised whenever `delete()` is attempted against an existing Compensation.

    Compensation Delete Integrity: `decision.md` §7/§17/§19 establish that a
    Compensation row, once it represents a real historical or currently
    effective business fact, may only be changed via a compensating
    correction (`corrects_id`, C2b) -- never overwritten, and (by the same
    principle, since permanent deletion destroys a historical business fact
    exactly as overwriting would) never deleted. Mirrors
    `AttendanceEventService`'s `AttendanceEventDeletionNotAllowedError`
    exactly: deletion is unconditionally rejected for every existing row,
    whether or not it has since been referenced by another row's
    `corrects_id`. This also replaces the previous behavior for a
    corrected row, which failed with a raw, unhandled `IntegrityError` from
    the `ON DELETE RESTRICT` FK on `corrects_id` -- that row is now
    rejected the same clean way as any other, before `repo.delete()` is
    ever called.
    """


class CompensationService:
    """Business logic for `Compensation`. Owns the transaction boundary via a UoW.

    Base Salary, represented by `Money`, effective-dated
    (`docs/architecture/capabilities/compensation/decision.md` §17):
    multiple rows may exist per employee, each a historical or current
    effective state. `create()` does not reject an employee who already
    has a `Compensation` row -- the old one-row-per-employee invariant is
    superseded (§17).

    Overlap and correction policy (§19, Accepted):

    - **Overlap (O1)**: a new row whose effective period overlaps an
      existing row for the same employee is rejected
      (`OverlappingCompensationPeriodError`), except against the exact row
      a correction row corrects.
    - **Correction (C2b)**: setting `corrects_id` on `CompensationCreate`
      creates a compensating correction row referencing the row it
      corrects; the corrected row is never mutated. `corrects_id` must
      reference an existing row belonging to the same employee.
    - **Correction precedence**: when resolving the effective row as of a
      date, if a correction row and the row it corrects are both
      candidates, the correction wins -- a Compensation-domain policy
      applied by `_exclude_corrected_targets`, not by
      `EffectiveDatingEvaluator` itself (which stays generic/mechanical,
      per its own docstring). Any other simultaneous match is genuine
      ambiguity and raises `AmbiguousEffectiveStateError`.

    `update()` is intentionally narrow: only `is_active` may be changed.
    Changing `base_salary_amount`, `base_salary_currency`, or the
    effective period of an existing row would mutate a historical business
    fact in place, which §7/§17 (Accepted) prohibit. Recording a new
    compensation state, or a correction, uses `create()`, not `update()`.

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
    read an arbitrary employee's effective Compensation while computing payroll,
    the same way `ApprovalService`/`ReconciliationService` operate outside
    per-request authorization scope elsewhere in this repository. When
    `request_context` is omitted, no authorization check runs. Every API-router
    call site supplies it, so the Owner Only policy is enforced end-to-end for
    actual user requests. `as_of_date` defaults to today -- Payroll's existing
    call site (`payroll_calculation.py`, not modified by this change) keeps
    working unchanged, per `decision.md` §18 (Option B4): Payroll's own
    as-of-date semantics remain a separate, deferred integration.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory
        self._evaluator = EffectiveDatingEvaluator()

    async def create(
        self, data: CompensationCreate, request_context: RequestContext
    ) -> Compensation:
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            await self._authorize(data, request_context)

            if data.corrects_id is not None:
                target = await repo.get(data.corrects_id)
                if target is None:
                    raise CorrectionTargetNotFoundError(str(data.corrects_id))
                if target.employee_id != data.employee_id:
                    raise CorrectionTargetEmployeeMismatchError(str(data.corrects_id))

            overlapping = await repo.find_overlapping_periods(
                data.employee_id,
                data.effective_from,
                data.effective_to,
                exclude_id=data.corrects_id,
            )
            if overlapping:
                raise OverlappingCompensationPeriodError(
                    f"Compensation period for employee {data.employee_id} "
                    "overlaps an existing period"
                )

            money = Money(data.base_salary_amount, data.base_salary_currency)

            compensation = await repo.create(
                employee_id=data.employee_id,
                base_salary_amount=money.amount,
                base_salary_currency=money.currency,
                effective_from=data.effective_from,
                effective_to=data.effective_to,
                corrects_id=data.corrects_id,
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
        self,
        employee_id: uuid.UUID,
        request_context: RequestContext | None = None,
        as_of_date: date | None = None,
    ) -> Compensation | None:
        """The `Compensation` row effective for `employee_id` as of `as_of_date`.

        `as_of_date` defaults to today. `is_active` plays no part in this
        resolution (`decision.md` §18, Option A3). Correction precedence
        is applied before the generic evaluator resolves the candidate
        set -- see `_exclude_corrected_targets` and the class docstring.
        Raises `AmbiguousEffectiveStateError` (propagated from
        `EffectiveDatingEvaluator.resolve`) if more than one unrelated row
        is effective as of `as_of_date`.
        """
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            resolved_date = as_of_date if as_of_date is not None else date.today()
            candidates = await repo.list_effective_as_of(employee_id, resolved_date)
            resolvable = self._exclude_corrected_targets(candidates)
            compensation = self._evaluator.resolve(resolvable, resolved_date)
            if compensation is None:
                return None
            if request_context is not None:
                await self._authorize(compensation, request_context)
            uow.session.expunge(compensation)
            return compensation

    @staticmethod
    def _exclude_corrected_targets(rows: Sequence[Compensation]) -> list[Compensation]:
        """Compensation-domain correction-precedence policy (`decision.md` §19):
        when a correction row and the row it corrects are both present in
        `rows`, the correction wins -- the corrected row is dropped before
        `EffectiveDatingEvaluator.resolve` sees the candidate set. This is
        Compensation's own policy, not Effective Dating's (see the class
        docstring and `effective_dating_evaluator.py`'s own docstring).
        """
        corrected_ids = {row.corrects_id for row in rows if row.corrects_id is not None}
        return [row for row in rows if row.id not in corrected_ids]

    async def list_history(self, request_context: RequestContext) -> Sequence[Compensation]:
        """Every historical `Compensation` row for the caller's own employee, oldest first.

        Scoped to the caller's own `employee_id` by construction, not
        authorized per-row -- mirrors `list()`'s existing pattern rather
        than introducing a new authorization shape.
        """
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            employee_id = request_context.employee_context.employee.id
            history = await repo.list_by_employee_id(employee_id)
            uow.session.expunge_all()
            return history

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

    async def list_active_as_of(self, as_of_date: date) -> Sequence[Compensation]:
        """Every `Compensation` row that is both `is_active=True` and
        effective as of `as_of_date`, unscoped across employees.

        Advanced Payroll's `PayrollCalculationService.calculate_batch`
        eligibility source (superseding `list_active` for that one caller,
        `implementation-plan.md` §1.1/§5): `is_active=True` alone can match
        more than one historical row per employee now that Compensation is
        effective-dated (`decision.md` §18), which `list_active` does not
        account for. Persistence-only: may return more than one row per
        `employee_id` (e.g. a correction and the row it corrects) --
        resolving down to one answer per employee remains
        `get_by_employee`'s job; callers of this method must deduplicate by
        `employee_id` before iterating and re-resolve each one via
        `get_by_employee`, exactly as `calculate_batch` does.
        """
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensations = await repo.list_active_as_of(as_of_date)
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
        """Toggles `is_active` on an existing row. Nothing else is updatable.

        `CompensationUpdate` intentionally carries only `is_active`
        (`schemas/compensation.py`) -- changing `base_salary_amount`,
        `base_salary_currency`, or the effective period of an existing row
        would mutate a historical business fact in place, which
        `decision.md` §7/§17 (Accepted) prohibit, and correcting an
        existing row remains an open Business/Product decision (§7,
        "Remaining Decision") not implemented here. Recording a new
        compensation state uses `create()`, not this method.
        """
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get(compensation_id)
            if compensation is None:
                return None

            await self._authorize(compensation, request_context)

            values = data.model_dump(exclude_unset=True)

            updated = await repo.update(compensation_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, compensation_id: uuid.UUID, request_context: RequestContext) -> bool:
        """Never succeeds for an existing row -- see `CompensationDeletionNotAllowedError`.

        Fetches and authorizes first, matching every other method's
        existing ordering (not-found before authorization; authorization
        before the delete-not-allowed rejection). `repo.delete()` is never
        called.
        """
        async with self._uow_factory() as uow:
            repo = CompensationRepository(uow.session)
            compensation = await repo.get(compensation_id)
            if compensation is None:
                return False

            await self._authorize(compensation, request_context)

            raise CompensationDeletionNotAllowedError(str(compensation_id))

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
