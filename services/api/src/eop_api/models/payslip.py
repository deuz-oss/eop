from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Payslip(BaseEntity):
    """Payslip's aggregate root (Iteration 1: frozen scope only).

    Immutable after creation, per
    `docs/architecture/capabilities/payslip/decision.md` §4-5: no service or
    API layer exposes `update`/`delete` for this entity. Scoped to one
    employee and one `PayrollRun` (`decision.md` §2-3).

    `gross_salary_amount`/`gross_salary_currency` and
    `net_salary_amount`/`net_salary_currency` each represent a `Money` value
    (`eop_api.foundation.monetary.types.Money`) -- `Money` has no
    persistence of its own, so this entity owns the plain columns that hold
    what each `Money` value represents. `PayslipService` does not compute
    either value; `PayrollCalculationService` computes them (Iteration 1
    rule: gross equals net -- no tax, BPJS, or deduction exists yet) and
    supplies both to `PayslipService.create` already-equal. Nullable at the
    database level only because these columns were added by a later
    migration to an already-existing table -- every payslip created via
    `PayslipService.create` going forward always has both.

    No tax, BPJS, attendance, leave, overtime, loan, reimbursement,
    proration, or currency-conversion field exists on this entity -- all are
    explicitly out of scope for Iteration 1 and deferred to a future
    iteration.
    """

    __tablename__ = "payslips"
    __table_args__ = (
        Index("ix_payslips_employee_id", "employee_id"),
        Index("ix_payslips_payroll_run_id", "payroll_run_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="RESTRICT"),
    )
    gross_salary_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), default=None
    )
    gross_salary_currency: Mapped[str | None] = mapped_column(String(3), default=None)
    net_salary_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), default=None)
    net_salary_currency: Mapped[str | None] = mapped_column(String(3), default=None)
