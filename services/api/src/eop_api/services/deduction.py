import uuid
from collections.abc import Callable, Sequence

from eop_api.core.payroll import PayrollRunStatus
from eop_api.foundation.monetary.types import Money
from eop_api.models.deduction import Deduction
from eop_api.repositories.deduction import DeductionRepository
from eop_api.repositories.deduction_type import DeductionTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.payroll_run import PayrollRunRepository
from eop_api.schemas.deduction import DeductionCreate, DeductionUpdate
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.deduction_authorization import DeductionAuthorizationEvaluator
from eop_api.services.employee_context import RequestContext
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Deduction does not exist."""


class DeductionTypeNotFoundError(Exception):
    """Raised when the DeductionType referenced by a Deduction does not exist."""


class PayrollRunNotFoundError(Exception):
    """Raised when the PayrollRun referenced by a Deduction does not exist."""


class PayrollRunCompletedError(Exception):
    """Raised when create/update/delete is attempted against a Deduction
    whose parent `PayrollRun.status == COMPLETED`. Mirrors Payslip's own
    completed-immutability boundary (E5) -- once a run is `COMPLETED`, its
    financial inputs are frozen, not only its output."""


class DeductionAuthorizationDeniedError(Exception):
    """Raised when the Deduction Authorization Policy (Owner Only) denies a
    `get`/`list` call."""


class DeductionService:
    """Business logic for `Deduction`. Owns the transaction boundary via a UoW.

    Owned by Payroll (already-decided exclusion, `compensation/decision.md`
    §4). `create`/`update`/`delete` take no `request_context` -- per
    `implementation-plan.md` §10.4, no public write route is exposed for
    this resource in v1 (no admin/payroll-actor authorization concept
    exists yet, `TECHNICAL_DEBT_REGISTER.md` TD-004); these methods are
    used internally/seeded directly. `get`/`list_by_employee` *are*
    Owner-Only authorized and exposed via API -- an employee may view their
    own deductions.

    Every mutating method rejects once the parent `PayrollRun` is
    `COMPLETED` (E5, D9) -- a completed run's financial inputs are frozen,
    matching Payslip's own immutability boundary.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: DeductionCreate) -> Deduction:
        async with self._uow_factory() as uow:
            repo = DeductionRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))
            if not await DeductionTypeRepository(uow.session).exists(data.deduction_type_id):
                raise DeductionTypeNotFoundError(str(data.deduction_type_id))

            payroll_run = await PayrollRunRepository(uow.session).get(data.payroll_run_id)
            if payroll_run is None:
                raise PayrollRunNotFoundError(str(data.payroll_run_id))
            if payroll_run.status == PayrollRunStatus.COMPLETED:
                raise PayrollRunCompletedError(str(data.payroll_run_id))

            money = Money(data.deduction_amount, data.deduction_currency)

            deduction = await repo.create(
                employee_id=data.employee_id,
                deduction_type_id=data.deduction_type_id,
                payroll_run_id=data.payroll_run_id,
                deduction_amount=money.amount,
                deduction_currency=money.currency,
                note=data.note,
            )
            await uow.commit()
            uow.session.expunge(deduction)
            return deduction

    async def get(
        self, deduction_id: uuid.UUID, request_context: RequestContext
    ) -> Deduction | None:
        async with self._uow_factory() as uow:
            repo = DeductionRepository(uow.session)
            deduction = await repo.get(deduction_id)
            if deduction is None:
                return None
            await self._authorize(deduction, request_context)
            uow.session.expunge(deduction)
            return deduction

    async def list_by_employee(self, request_context: RequestContext) -> Sequence[Deduction]:
        """Deduction records owned by the caller's own `employee_id`,
        across every payroll run."""
        async with self._uow_factory() as uow:
            repo = DeductionRepository(uow.session)
            employee_id = request_context.employee_context.employee.id
            deductions = await repo.list_by_employee(employee_id)
            uow.session.expunge_all()
            return deductions

    async def list_by_employee_and_payroll_run(
        self, employee_id: uuid.UUID, payroll_run_id: uuid.UUID
    ) -> Sequence[Deduction]:
        """Used only by `PayrollCalculationService` (no authorization --
        system-driven payroll computation, mirrors
        `CompensationService.get_by_employee`'s trusted-internal-caller
        pattern)."""
        async with self._uow_factory() as uow:
            repo = DeductionRepository(uow.session)
            deductions = await repo.list_by_employee_and_payroll_run(employee_id, payroll_run_id)
            uow.session.expunge_all()
            return deductions

    async def update(self, deduction_id: uuid.UUID, data: DeductionUpdate) -> Deduction | None:
        async with self._uow_factory() as uow:
            repo = DeductionRepository(uow.session)
            deduction = await repo.get(deduction_id)
            if deduction is None:
                return None

            payroll_run = await PayrollRunRepository(uow.session).get(deduction.payroll_run_id)
            if payroll_run is not None and payroll_run.status == PayrollRunStatus.COMPLETED:
                raise PayrollRunCompletedError(str(deduction.payroll_run_id))

            values = data.model_dump(exclude_unset=True)
            if "deduction_amount" in values or "deduction_currency" in values:
                money = Money(
                    values.get("deduction_amount", deduction.deduction_amount),
                    values.get("deduction_currency", deduction.deduction_currency),
                )
                values["deduction_amount"] = money.amount
                values["deduction_currency"] = money.currency

            updated = await repo.update(deduction_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, deduction_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = DeductionRepository(uow.session)
            deduction = await repo.get(deduction_id)
            if deduction is None:
                return False

            payroll_run = await PayrollRunRepository(uow.session).get(deduction.payroll_run_id)
            if payroll_run is not None and payroll_run.status == PayrollRunStatus.COMPLETED:
                raise PayrollRunCompletedError(str(deduction.payroll_run_id))

            deleted = await repo.delete(deduction_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, deduction: Deduction, request_context: RequestContext) -> None:
        authorization_request = AuthorizationRequest(context=request_context, resource=deduction)
        decision = AuthorizationService(DeductionAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise DeductionAuthorizationDeniedError(
                decision.reason or "Deduction authorization denied"
            )
