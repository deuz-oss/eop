from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Deduction(BaseEntity):
    """One employee's explicit, non-statutory deduction for one `PayrollRun` (D7).

    Owned by Payroll (already-decided exclusion, `compensation/decision.md`
    §4). Deliberately an explicit, per-`(employee, payroll_run)` record, not
    a recurring/effective-dated entitlement -- recurring deductions (e.g. an
    auto-repeating loan installment) are out of scope for v1
    (`docs/architecture/capabilities/payroll-calculation/
    implementation-plan.md` §3.1): inventing recurrence/termination
    semantics would assert business content nobody has specified. An admin
    enters one `Deduction` row per run it applies to.

    Mutable (via `DeductionService.update`/`.delete`) only while the parent
    `PayrollRun.status != COMPLETED` -- mirrors Payslip's own
    completed-immutability boundary (E5), enforced in the service layer,
    not by a database constraint (no repository precedent anywhere in this
    codebase enforces a cross-table state guard at the schema level).

    `deduction_amount`/`deduction_currency` together represent a `Money`
    value (`eop_api.foundation.monetary.types.Money`), same pattern as
    `Compensation`/`Payslip`.
    """

    __tablename__ = "deductions"
    __table_args__ = (
        Index("ix_deductions_employee_id", "employee_id"),
        Index("ix_deductions_payroll_run_id", "payroll_run_id"),
        Index("ix_deductions_deduction_type_id", "deduction_type_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    deduction_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deduction_types.id", ondelete="RESTRICT"),
    )
    payroll_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payroll_runs.id", ondelete="RESTRICT"),
    )
    deduction_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    deduction_currency: Mapped[str] = mapped_column(String(3))
    note: Mapped[str | None] = mapped_column(String(500), default=None)
