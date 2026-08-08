from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Compensation(BaseEntity):
    """One employee's current Base Salary (Iteration 1: frozen scope only).

    `employee_id` is `UniqueConstraint`-enforced: exactly one `Compensation`
    row may exist per `HrEmployee` at a time -- this is the mechanism, not
    merely a convention, behind "one active Compensation per Employee".
    `ON DELETE RESTRICT` matches every other FK into `HrEmployee` from HR
    data.

    `base_salary_amount`/`base_salary_currency` together represent a `Money`
    value (`eop_api.foundation.monetary.types.Money`). `Money` itself has no
    persistence of its own, so this entity owns the two plain columns that
    hold what a `Money` value represents; `CompensationService` constructs
    and validates `Money` at the service boundary, not here.

    No allowance, bonus, deduction, salary component, approval workflow, or
    history/versioning field exists on this entity -- all are out of scope
    for Iteration 1's frozen business scope and explicitly deferred to a
    future iteration.

    `is_active` allows a `Compensation` record to be deactivated (e.g. no
    longer considered by payroll processing) without deleting it or
    violating the one-row-per-employee constraint -- it does not introduce
    a second row or any historical record of a prior value.
    """

    __tablename__ = "compensations"
    __table_args__ = (
        UniqueConstraint("employee_id", name="uq_compensations_employee_id"),
        Index("ix_compensations_employee_id", "employee_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    base_salary_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    base_salary_currency: Mapped[str] = mapped_column(String(3))
    effective_from: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
