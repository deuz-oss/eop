import uuid
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from eop_api.foundation.monetary.types import Money
from eop_api.models.allowance import Allowance
from eop_api.repositories.allowance import AllowanceRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.schemas.allowance import AllowanceCreate, AllowanceUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.allowance_authorization import AllowanceAuthorizationEvaluator
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.effective_dating_evaluator import EffectiveDatingEvaluator
from eop_api.services.employee_context import RequestContext
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by an Allowance does not exist."""


class CorrectionTargetNotFoundError(Exception):
    """Raised when `AllowanceCreate.corrects_id` does not reference an
    existing Allowance row."""


class CorrectionTargetEmployeeMismatchError(Exception):
    """Raised when `AllowanceCreate.corrects_id` references an Allowance row
    belonging to a different employee than `AllowanceCreate.employee_id`."""


class OverlappingAllowancePeriodError(Exception):
    """Raised when a new Allowance row's effective period overlaps an
    existing row for the same `(employee_id, allowance_type)`. A correction
    row (`corrects_id` set) is exempt only against the exact row it
    corrects."""


class AllowanceAuthorizationDeniedError(Exception):
    """Raised when the Allowance Authorization Policy (Owner Only) denies a
    create/get/update/delete call."""


class AllowanceService:
    """Business logic for `Allowance`. Owns the transaction boundary via a UoW.

    Owned by the Compensation capability (D6). Mirrors `CompensationService`
    directly -- effective-dated, multi-row per `(employee_id,
    allowance_type)`, overlap rejection (O1-equivalent), compensating
    correction (C2b-equivalent) -- with every operation additionally scoped
    by `allowance_type` per D6's "multiple simultaneous allowances"
    requirement.

    `update()` is intentionally narrow: only `is_active` may be changed,
    for the same reason as `CompensationService.update` -- changing the
    amount/currency/effective period of an existing row would mutate a
    historical business fact in place.

    `list_active_for_employee` is the read-only entry point
    `PayrollCalculationService` uses (no `request_context`, no
    authorization -- mirrors `CompensationService.get_by_employee`'s
    trusted-internal-caller pattern).
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory
        self._evaluator = EffectiveDatingEvaluator()

    async def create(self, data: AllowanceCreate, request_context: RequestContext) -> Allowance:
        async with self._uow_factory() as uow:
            repo = AllowanceRepository(uow.session)

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
                data.allowance_type,
                data.effective_from,
                data.effective_to,
                exclude_id=data.corrects_id,
            )
            if overlapping:
                raise OverlappingAllowancePeriodError(
                    f"Allowance period for employee {data.employee_id}, "
                    f"type {data.allowance_type!r} overlaps an existing period"
                )

            money = Money(data.allowance_amount, data.allowance_currency)

            allowance = await repo.create(
                employee_id=data.employee_id,
                allowance_type=data.allowance_type,
                allowance_amount=money.amount,
                allowance_currency=money.currency,
                effective_from=data.effective_from,
                effective_to=data.effective_to,
                corrects_id=data.corrects_id,
            )
            await uow.commit()
            uow.session.expunge(allowance)
            return allowance

    @staticmethod
    def _exclude_corrected_targets(rows: Sequence[Allowance]) -> list[Allowance]:
        """Mirrors `CompensationService._exclude_corrected_targets` exactly.

        Defined here, before any method named `list` in this class, so this
        signature's `list[Allowance]` resolves to the builtin `list` --
        matching `CompensationService`'s own method ordering, not an
        arbitrary choice (a method literally named `list` defined earlier
        in the class body shadows the builtin for every later signature
        evaluated in the same class namespace).
        """
        corrected_ids = {row.corrects_id for row in rows if row.corrects_id is not None}
        return [row for row in rows if row.id not in corrected_ids]

    async def get(
        self, allowance_id: uuid.UUID, request_context: RequestContext
    ) -> Allowance | None:
        async with self._uow_factory() as uow:
            repo = AllowanceRepository(uow.session)
            allowance = await repo.get(allowance_id)
            if allowance is None:
                return None
            await self._authorize(allowance, request_context)
            uow.session.expunge(allowance)
            return allowance

    async def list(self, request_context: RequestContext) -> Sequence[Allowance]:
        """Allowance records owned by the caller's own `employee_id`."""
        async with self._uow_factory() as uow:
            repo = AllowanceRepository(uow.session)
            allowances = await repo.list()
            current_employee_id = request_context.employee_context.employee.id
            owned = [a for a in allowances if a.employee_id == current_employee_id]
            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self,
        request_context: RequestContext,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Allowance]:
        async with self._uow_factory() as uow:
            repo = AllowanceRepository(uow.session)
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

    async def list_history(self, request_context: RequestContext) -> Sequence[Allowance]:
        """Every historical Allowance row for the caller's own employee."""
        async with self._uow_factory() as uow:
            repo = AllowanceRepository(uow.session)
            employee_id = request_context.employee_context.employee.id
            history = await repo.list_by_employee_id(employee_id)
            uow.session.expunge_all()
            return history

    async def list_active_for_employee(
        self, employee_id: uuid.UUID, as_of_date: date
    ) -> Sequence[Allowance]:
        """Every Allowance effective for `employee_id` as of `as_of_date`,
        across all `allowance_type`s. Used only by
        `PayrollCalculationService` (no `request_context`, no
        authorization -- system-driven payroll computation, not a request
        acting on behalf of one employee, mirrors
        `CompensationService.get_by_employee`).
        """
        async with self._uow_factory() as uow:
            repo = AllowanceRepository(uow.session)
            candidates = await repo.list_effective_as_of_any_type(employee_id, as_of_date)
            by_type: dict[str, list[Allowance]] = {}
            for row in candidates:
                by_type.setdefault(row.allowance_type, []).append(row)

            resolved: list[Allowance] = []
            for rows in by_type.values():
                resolvable = self._exclude_corrected_targets(rows)
                resolved_row = self._evaluator.resolve(resolvable, as_of_date)
                if resolved_row is not None:
                    resolved.append(resolved_row)

            uow.session.expunge_all()
            return resolved

    async def update(
        self, allowance_id: uuid.UUID, data: AllowanceUpdate, request_context: RequestContext
    ) -> Allowance | None:
        async with self._uow_factory() as uow:
            repo = AllowanceRepository(uow.session)
            allowance = await repo.get(allowance_id)
            if allowance is None:
                return None

            await self._authorize(allowance, request_context)

            values = data.model_dump(exclude_unset=True)
            updated = await repo.update(allowance_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, allowance_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = AllowanceRepository(uow.session)
            allowance = await repo.get(allowance_id)
            if allowance is None:
                return False

            await self._authorize(allowance, request_context)

            deleted = await repo.delete(allowance_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(AllowanceAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise AllowanceAuthorizationDeniedError(
                decision.reason or "Allowance authorization denied"
            )
