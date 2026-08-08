from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity
from eop_api.db.mixins import EffectiveDatingMixin


class PayrollStatutoryParameter(BaseEntity, EffectiveDatingMixin):
    """A named, effective-dated, configurable payroll parameter.

    Implements D2/E4 (`docs/architecture/capabilities/payroll-calculation/
    business-decision-package.md`): statutory rules/parameters are
    configurable data; the calculation engine (`services/payroll/*.py`)
    stays code-based. This is a generic key/value store, not a rule or
    expression engine -- it holds only named numeric values, never a
    formula, condition, or executable expression. `key` is free-form
    (e.g. `STATUTORY_TAX_RATE`, `OVERTIME_MULTIPLIER_WEEKDAY`,
    `STANDARD_WORKING_DAYS_PER_MONTH`, `STANDARD_DAILY_HOURS`) -- no fixed
    vocabulary is asserted here, since no parameter catalog content has
    been specified.

    Effective-dated (`EffectiveDatingMixin`, mechanically reused per the
    already-approved Effective Dating mechanism -- no new architecture
    decision): parameters change over time (e.g. an annual tax-rate
    change) without losing the value that applied to an earlier period.

    `value` uses `Numeric(18, 6)` rather than the `Numeric(14, 2)`/`Money`
    convention used for monetary columns elsewhere: a parameter is a rate
    or multiplier (e.g. `1.5`, `0.05`), not a currency-scoped monetary
    amount, so it deliberately does not use `Money`.

    Overlap policy mirrors Compensation's O1 exactly (`decision.md` §19),
    scoped per `key` instead of per `employee_id`: two values for the same
    `key` may not have overlapping effective periods.
    """

    __tablename__ = "payroll_statutory_parameters"
    __table_args__ = (
        Index("ix_payroll_statutory_parameters_key_effective", "key", "effective_from"),
    )

    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[Decimal] = mapped_column(Numeric(18, 6))
    description: Mapped[str | None] = mapped_column(String(500), default=None)
