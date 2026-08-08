from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Index, String, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.core.payroll import PayrollRunStatus
from eop_api.db.base import BaseEntity


class PayrollRun(BaseEntity):
    """The Payroll bounded context's aggregate root.

    Deliberately not employee-scoped -- that role belongs to `Payslip`, not to
    `PayrollRun` itself, per
    `docs/architecture/capabilities/payroll/decision.md` §2-3 and §6.
    `code` is globally unique, `name` is a paired human-readable label,
    matching the identity shape already used by `EmploymentType`/
    `EmploymentStatus`/`JobGrade`/`Shift`/`Holiday`.

    `status` (`PayrollRunStatus`, `DRAFT -> PROCESSING -> COMPLETED`) is the
    lifecycle boundary for one payroll batch, decided in
    `docs/architecture/capabilities/payroll/decision.md` Addendum (Version 2)
    §1 -- new for Iteration 2. No monetary field exists on this entity:
    computation logic and monetary amounts belong to `Payslip`, not to
    `PayrollRun`.

    `period_start`/`period_end` implement E6 (`PayrollRun` owns the payroll
    period) and D1 (monthly cadence): `PayrollRunService.create` validates
    they form exactly one calendar month -- no separate `PayPeriod` entity
    is introduced (`implementation-plan.md` §3.2/E6). `currency` implements
    D8/E7 (one currency per `PayrollRun`); `PayrollCalculationService`
    excludes any employee whose `Compensation` currency does not match it.

    All three are nullable at the database level only because they were
    added by a later migration to an already-existing table -- the same
    reason `Payslip.gross_salary_amount`/`net_salary_amount` are nullable
    (`models/payslip.py`). Every `PayrollRun` created going forward always
    has all three; existing Iteration 1-3 rows keep them `NULL`, an
    accepted historical gap, not a data-loss risk.
    """

    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("code", name="uq_payroll_runs_code"),
        Index("ix_payroll_runs_name", "name"),
        Index("ix_payroll_runs_period_currency", "period_start", "period_end", "currency"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[PayrollRunStatus] = mapped_column(
        SqlEnum(PayrollRunStatus, name="payroll_run_status", native_enum=False, length=20),
        default=PayrollRunStatus.DRAFT,
    )
    period_start: Mapped[date | None] = mapped_column(Date, default=None)
    period_end: Mapped[date | None] = mapped_column(Date, default=None)
    currency: Mapped[str | None] = mapped_column(String(3), default=None)
