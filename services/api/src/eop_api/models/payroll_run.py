from __future__ import annotations

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import Index, String, UniqueConstraint
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
    """

    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("code", name="uq_payroll_runs_code"),
        Index("ix_payroll_runs_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[PayrollRunStatus] = mapped_column(
        SqlEnum(PayrollRunStatus, name="payroll_run_status", native_enum=False, length=20),
        default=PayrollRunStatus.DRAFT,
    )
