import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.foundation.monetary.types import Money
from eop_api.models.payslip import Payslip
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.payroll_run import PayrollRunRepository
from eop_api.repositories.payslip import PayslipRepository
from eop_api.schemas.payslip import PayslipCreate
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.services.payslip_authorization import PayslipAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Payslip does not exist."""


class PayrollRunNotFoundError(Exception):
    """Raised when the PayrollRun referenced by a Payslip does not exist."""


class PayslipAuthorizationDeniedError(Exception):
    """Raised when the Payslip Authorization Policy (Owner Only,
    `docs/architecture/capabilities/payslip/decision.md` §8 Addendum) denies a
    create/get call -- i.e. `AuthorizationDecision.allowed` is `False`.

    Thrown only by `PayslipService`, never by `PayslipAuthorizationEvaluator`
    or `AuthorizationService` themselves.
    """


class PayslipService:
    """Business logic for `Payslip`. Owns the transaction boundary via a UoW.

    `Payslip` is immutable after creation, per
    `docs/architecture/capabilities/payslip/decision.md` §4-5: this service
    exposes `create`/`get`/`list` only -- no `update`, no `delete`, no
    computation, no orchestration.

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
        self, data: PayslipCreate, request_context: RequestContext | None = None
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
            await uow.commit()
            uow.session.expunge(payslip)
            return payslip

    async def get(
        self, payslip_id: uuid.UUID, request_context: RequestContext
    ) -> Payslip | None:
        async with self._uow_factory() as uow:
            repo = PayslipRepository(uow.session)
            payslip = await repo.get(payslip_id)
            if payslip is None:
                return None
            await self._authorize(payslip, request_context)
            uow.session.expunge(payslip)
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
            uow.session.expunge_all()
            return owned

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
            raise PayslipAuthorizationDeniedError(
                decision.reason or "Payslip authorization denied"
            )
