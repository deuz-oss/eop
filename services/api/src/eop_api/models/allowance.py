from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity
from eop_api.db.mixins import EffectiveDatingMixin


class Allowance(BaseEntity, EffectiveDatingMixin):
    """One employee's effective-dated allowance (multiple rows per employee).

    Owned by the Compensation capability, per D6
    (`docs/architecture/capabilities/payroll-calculation/
    business-decision-package.md`): "Compensation owns allowance
    definition/value; Payroll consumes effective state." Physically a
    separate model file the same way `JobGrade`/`EmploymentType` are
    separate files within one HR domain -- not a new capability.

    Mirrors `Compensation`'s shape directly (`models/compensation.py`):
    effective-dated, multi-row per employee, `is_active` independent of
    temporal validity, `corrects_id` for compensating correction. The one
    difference is `allowance_type`: an employee may hold multiple
    *simultaneous* allowances of different types
    (`compensation/decision.md` §4: "may require multiple simultaneous
    values"), so overlap is scoped to `(employee_id, allowance_type)`,
    not `employee_id` alone -- two different types may have overlapping
    periods; two rows of the *same* type may not.

    `allowance_type` is a free-form code (e.g. `TRANSPORT`, `MEAL`), not a
    fixed enum -- no allowance catalog content has been specified;
    asserting one here would be inventing business content this
    capability does not have.

    `allowance_amount`/`allowance_currency` together represent a `Money`
    value (`eop_api.foundation.monetary.types.Money`), constructed and
    validated at the service boundary, mirroring `Compensation`'s own
    `base_salary_amount`/`base_salary_currency` pattern exactly.
    """

    __tablename__ = "allowances"
    __table_args__ = (
        Index(
            "ix_allowances_employee_type_effective",
            "employee_id",
            "allowance_type",
            "effective_from",
        ),
        Index("ix_allowances_corrects_id", "corrects_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    allowance_type: Mapped[str] = mapped_column(String(50))
    allowance_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    allowance_currency: Mapped[str] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    corrects_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("allowances.id", ondelete="RESTRICT"), default=None
    )
