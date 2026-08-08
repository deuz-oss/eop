import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.core.payroll import PayrollRunStatus
from eop_api.foundation.monetary.types import Money
from eop_api.models.payslip import Payslip
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.payroll_run import PayrollRunRepository
from eop_api.repositories.payslip import PayslipRepository
from eop_api.repositories.payslip_line_item import PayslipLineItemRepository
from eop_api.schemas.payslip import PayslipCreate
from eop_api.schemas.payslip_line_item import PayslipLineItemCreate
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.services.payslip_authorization import PayslipAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Payslip does not exist."""


class PayrollRunNotFoundError(Exception):
    """Raised when the PayrollRun referenced by a Payslip does not exist."""


class PayrollRunCompletedError(Exception):
    """Raised when `delete_by_payroll_run` is attempted against a
    `COMPLETED` `PayrollRun`. Preserves E5's immutability boundary for this
    internal-only path -- `PayrollCalculationService` already checks this
    before calling, but this method does not trust that alone (defense in
    depth)."""


class PayslipAuthorizationDeniedError(Exception):
    """Raised when the Payslip Authorization Policy (Owner Only,
    `docs/architecture/capabilities/payslip/decision.md` §8 Addendum) denies a
    create/get call -- i.e. `AuthorizationDecision.allowed` is `False`.

    Thrown only by `PayslipService`, never by `PayslipAuthorizationEvaluator`
    or `AuthorizationService` themselves.
    """


class PayslipService:
    """Business logic for `Payslip`. Owns the transaction boundary via a UoW.

    `Payslip` remains immutable after creation via its **public** contract,
    per `docs/architecture/capabilities/payslip/decision.md` §4-5: this
    service exposes `create`/`get`/`list` at the API layer -- no `update`,
    no public `delete`. `delete_by_payroll_run` is a new, deliberately
    **internal-only** method (Advanced Payroll, E5/D9 --
    `implementation-plan.md` §3.3): it exists solely to power
    `PayrollCalculationService`'s pre-completion rerun, is never routed by
    any API endpoint, and itself refuses once the parent `PayrollRun` is
    `COMPLETED`. This is how "immutable completed results" (E5) and "rerun
    allowed before completion" (D9) coexist without weakening Payslip's
    public immutability contract.

    `create`/`get`/`list` are gated by the Payslip Authorization Policy (Owner
    Only): authorization is delegated to `AuthorizationService`/
    `PayslipAuthorizationEvaluator` via `_authorize`, and a denied decision
    raises `PayslipAuthorizationDeniedError`. `list` is scoped to the caller's
    own `employee_id` rather than authorized per-item, mirroring
    `AttendanceEventService`.

    `create`'s `request_context` is optional: `PayrollCalculationService`
    calls it internally (not on behalf of a specific authenticated request) to
    compute and persist a Payslip for an arbitrary employee, the same way
    `ApprovalService`/`ReconciliationService` operate outside per-request
    authorization scope elsewhere in this repository. When `request_context`
    is omitted, no authorization check runs. The API router always supplies
    it, so the Owner Only policy is enforced end-to-end for actual user
    requests. `get_by_employee_and_payroll_run` is not exposed via any API
    route (used only by `PayrollCalculationService`'s internal duplicate
    check), so it is not authorization-gated.

    `create`'s optional `line_items` (E1 -- structured calculation result,
    Advanced Payroll): persisted in the same transaction as the `Payslip`
    row via `PayslipLineItemRepository`, then attached as a plain Python
    attribute (`payslip.line_items = ...`) before `expunge` -- deliberately
    **not** a declared SQLAlchemy `relationship()`, to avoid async
    lazy-load/expunge complexity. The public `POST /payslips` route's
    `PayslipCreate` schema does not accept line items; only
    `PayrollCalculationService`'s internal call supplies them.

    Returned entities are expunged from the unit-of-work's session before it
    closes: the UoW always rolls back (and thus expires all attributes) on
    exit, so callers holding on to the entity after this method returns would
    otherwise hit a `DetachedInstanceError` on first attribute access.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(
        self,
        data: PayslipCreate,
        request_context: RequestContext | None = None,
        line_items: Sequence[PayslipLineItemCreate] = (),
    ) -> Payslip:
        async with self._uow_factory() as uow:
            repo = PayslipRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if not await PayrollRunRepository(uow.session).exists(data.payroll_run_id):
                raise PayrollRunNotFoundError(str(data.payroll_run_id))

            if request_context is not None:
                await self._authorize(data, request_context)

            gross = Money(data.gross_salary_amount, data.gross_salary_currency)
            net = Money(data.net_salary_amount, data.net_salary_currency)

            payslip = await repo.create(
                employee_id=data.employee_id,
                payroll_run_id=data.payroll_run_id,
                gross_salary_amount=gross.amount,
                gross_salary_currency=gross.currency,
                net_salary_amount=net.amount,
                net_salary_currency=net.currency,
            )

            line_item_repo = PayslipLineItemRepository(uow.session)
            created_items = []
            for item in line_items:
                money = Money(item.line_amount, item.line_currency)
                created_items.append(
                    await line_item_repo.create(
                        payslip_id=payslip.id,
                        component_type=item.component_type,
                        label=item.label,
                        line_amount=money.amount,
                        line_currency=money.currency,
                        source_id=item.source_id,
                    )
                )

            await uow.commit()

            payslip.line_items = created_items  # type: ignore[attr-defined]
            uow.session.expunge(payslip)
            for created_item in created_items:
                uow.session.expunge(created_item)
            return payslip

    async def get(self, payslip_id: uuid.UUID, request_context: RequestContext) -> Payslip | None:
        async with self._uow_factory() as uow:
            repo = PayslipRepository(uow.session)
            payslip = await repo.get(payslip_id)
            if payslip is None:
                return None
            await self._authorize(payslip, request_context)
            items = await PayslipLineItemRepository(uow.session).list_by_payslip(payslip_id)
            payslip.line_items = list(items)  # type: ignore[attr-defined]
            uow.session.expunge(payslip)
            for item in items:
                uow.session.expunge(item)
            return payslip

    async def get_by_employee_and_payroll_run(
        self, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
    ) -> Payslip | None:
        async with self._uow_factory() as uow:
            repo = PayslipRepository(uow.session)
            payslip = await repo.get_by_employee_and_payroll_run(employee_id, payroll_run_id)
            if payslip is not None:
                uow.session.expunge(payslip)
            return payslip

    async def list(self, request_context: RequestContext) -> Sequence[Payslip]:
        """Payslips owned by the caller's own `employee_id`."""
        async with self._uow_factory() as uow:
            repo = PayslipRepository(uow.session)
            payslips = await repo.list()
            current_employee_id = request_context.employee_context.employee.id
            owned = [p for p in payslips if p.employee_id == current_employee_id]
            line_item_repo = PayslipLineItemRepository(uow.session)
            for payslip in owned:
                items = await line_item_repo.list_by_payslip(payslip.id)
                payslip.line_items = list(items)  # type: ignore[attr-defined]
            uow.session.expunge_all()
            return owned

    async def delete_by_payroll_run(self, payroll_run_id: uuid.UUID) -> int:
        """Deletes every `Payslip` (and its line items, via `ON DELETE
        CASCADE`) belonging to `payroll_run_id`.

        Internal-only -- not exposed via any API route. Guarded: raises
        `PayrollRunCompletedError` if the parent run is `COMPLETED`,
        preserving E5's immutability boundary even for this internal path.
        A no-op (returns `0`) if no Payslips exist for the run yet (the
        first `calculate_batch` call for a run).
        """
        async with self._uow_factory() as uow:
            payroll_run = await PayrollRunRepository(uow.session).get(payroll_run_id)
            if payroll_run is not None and payroll_run.status == PayrollRunStatus.COMPLETED:
                raise PayrollRunCompletedError(str(payroll_run_id))

            repo = PayslipRepository(uow.session)
            existing = await repo.list_by_payroll_run(payroll_run_id)
            count = 0
            for payslip in existing:
                await repo.delete(payslip.id)
                count += 1
            if count:
                await uow.commit()
            return count

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Payslip Authorization Policy (Owner Only) for `resource`.

        `resource` is the `PayslipCreate` payload for `create`, or the
        already-loaded `Payslip` for `get`. This method only delegates to
        `AuthorizationService`/`PayslipAuthorizationEvaluator`; it contains no
        comparison of its own, so `PayslipService` never evaluates
        authorization itself.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(PayslipAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise PayslipAuthorizationDeniedError(decision.reason or "Payslip authorization denied")
