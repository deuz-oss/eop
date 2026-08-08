from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity
from eop_api.db.mixins import EffectiveDatingMixin


class Compensation(BaseEntity, EffectiveDatingMixin):
    """One employee's Base Salary, effective-dated (multiple rows per employee).

    `docs/architecture/capabilities/compensation/decision.md` §17: the
    history/retention decision (§7) applies to this aggregate itself --
    multiple `Compensation` rows may exist per `employee_id`, each a
    historical or current effective state. There is deliberately no
    uniqueness constraint on `employee_id` (removed from the Iteration 1
    schema this addendum superseded) and no "exactly one active row"
    invariant -- which row is temporally current is resolved by
    `EffectiveDatingEvaluator`, not by any column or constraint here.
    `ON DELETE RESTRICT` matches every other FK into `HrEmployee` from HR
    data.

    `effective_from`/`effective_to` come from `EffectiveDatingMixin`
    (`db/mixins.py`), not defined on this entity directly.

    `base_salary_amount`/`base_salary_currency` together represent a `Money`
    value (`eop_api.foundation.monetary.types.Money`). `Money` itself has no
    persistence of its own, so this entity owns the two plain columns that
    hold what a `Money` value represents; `CompensationService` constructs
    and validates `Money` at the service boundary, not here.

    No allowance, bonus, deduction, or salary component field exists on
    this entity -- out of scope, deferred to a future iteration
    (`compensation/decision.md` §4).

    `is_active` is a business/eligibility flag, independent of temporal
    validity (`decision.md` §18, Option A3) -- it is Payroll's existing
    eligibility signal (`payroll/decision.md` Version 3 Addendum §5),
    *not* an indicator of which row is temporally current. It applies
    per-row and is not reinterpreted by the multi-row model.

    Overlap permission and correction behavior are resolved
    (`decision.md` §19, Accepted):

    - Overlapping effective periods for the same employee are rejected by
      `CompensationService`, not enforced by a database constraint
      (`decision.md` §19 -- "service-layer business validation"; no
      partial-unique/exclusion-constraint precedent exists anywhere in
      this repository).
    - `corrects_id` is a nullable self-reference identifying the row a
      correction row corrects. Mirrors `Department.parent_id`/
      `HrEmployee.manager_id`'s exact shape: nullable, `ON DELETE
      RESTRICT`, named without repeating the entity name. `NULL` means an
      ordinary row; non-`NULL` means a compensating correction
      (`decision.md` §19, Option C2b). The corrected row is never mutated.
    """

    __tablename__ = "compensations"
    __table_args__ = (
        Index("ix_compensations_employee_effective", "employee_id", "effective_from"),
        Index("ix_compensations_corrects_id", "corrects_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    base_salary_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    base_salary_currency: Mapped[str] = mapped_column(String(3))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    corrects_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("compensations.id", ondelete="RESTRICT"), default=None
    )
