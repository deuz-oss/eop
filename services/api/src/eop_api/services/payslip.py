import uuid
from collections.abc import Callable, Sequence

from eop_api.foundation.monetary.types import Money
from eop_api.models.payslip import Payslip
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.payroll_run import PayrollRunRepository
from eop_api.repositories.payslip import PayslipRepository
from eop_api.schemas.payslip import PayslipCreate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Payslip does not exist."""


class PayrollRunNotFoundError(Exception):
    """Raised when the PayrollRun referenced by a Payslip does not exist."""


class PayslipService:
    """Business logic for `Payslip`. Owns the transaction boundary via a UoW.

    `Payslip` is immutable after creation, per
    `docs/architecture/capabilities/payslip/decision.md` §4-5: this service
    exposes `create`/`get`/`list` only -- no `update`, no `delete`, no
    computation, no orchestration, no authorization.

    Returned entities are expunged from the unit-of-work's session before it
    closes: the UoW always rolls back (and thus expires all attributes) on
    exit, so callers holding on to the entity after this method returns would
    otherwise hit a `DetachedInstanceError` on first attribute access.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: PayslipCreate) -> Payslip:
        async with self._uow_factory() as uow:
            repo = PayslipRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if not await PayrollRunRepository(uow.session).exists(data.payroll_run_id):
                raise PayrollRunNotFoundError(str(data.payroll_run_id))

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

    async def get(self, payslip_id: uuid.UUID) -> Payslip | None:
        async with self._uow_factory() as uow:
            repo = PayslipRepository(uow.session)
            payslip = await repo.get(payslip_id)
            if payslip is not None:
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

    async def list(self) -> Sequence[Payslip]:
        async with self._uow_factory() as uow:
            repo = PayslipRepository(uow.session)
            payslips = await repo.list()
            uow.session.expunge_all()
            return payslips
