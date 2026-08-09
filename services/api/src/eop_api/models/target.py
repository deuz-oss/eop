from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.hr_employee import HrEmployee
    from eop_api.models.kpi import Kpi


class Target(BaseEntity):
    """One KPI goal assigned to one employee for one calendar month.
    Performance Management, Target Iteration 1.

    Ownership scope is Employee (`docs/architecture/capabilities/performance/
    target-iteration-1-scope-and-implementation-plan.md` §3, CPO/CTO
    decision) -- deliberately not Store, Organization, or Territory/Region/
    Area, the latter remaining blocked by the unresolved Phase 3
    Organization Hierarchy gate and not introduced as a new dependency here.

    `employee_id` is the Target's business scope (whose goal this is), not
    its authorization boundary -- authorization is Role Based
    (`RequireRole("admin")`, §8): a Target is assigned by an administrator,
    not self-authored by the employee, so no Owner Only evaluator exists for
    this entity, unlike `Visit`/`Survey`/`Compensation`.

    `period_year`/`period_month` (§7) extend `LeaveBalance.period_year`'s
    existing single-integer-field convention to month granularity, rather
    than `PayrollRun`'s heavier `period_start`/`period_end` date-range shape
    -- Target's period is always exactly one discrete calendar month, with
    nothing to range-validate beyond `period_month` in `[1, 12]`, enforced
    at the Pydantic schema boundary (`schemas/target.py`), matching this
    repository's convention of no `CheckConstraint` usage in `models/`.

    `goal_value` is `Numeric(18, 6)`, mirroring
    `PayrollStatutoryParameter.value`'s precedent for a generic,
    non-monetary numeric value -- not `Numeric(14, 2)`/`Money`, since
    `goal_value` is not currency. No `unit` column: it is read from the
    referenced `Kpi.unit` at presentation time, never duplicated (§4).

    Both `kpi_id` and `employee_id` are `ON DELETE RESTRICT`, matching every
    other FK into `Kpi`/`HrEmployee` in this repository -- target history
    must be preserved, not silently cascaded away.

    At most one `Target` may exist per `(employee_id, kpi_id, period_year,
    period_month)`, enforced at the database level (§6), mirroring
    `Survey.visit_id`'s own `UniqueConstraint` precedent.
    """

    __tablename__ = "targets"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "kpi_id",
            "period_year",
            "period_month",
            name="uq_targets_employee_kpi_period",
        ),
        Index("ix_targets_employee_id", "employee_id"),
        Index("ix_targets_kpi_id", "kpi_id"),
    )

    kpi_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("kpis.id", ondelete="RESTRICT"),
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    period_year: Mapped[int] = mapped_column(Integer)
    period_month: Mapped[int] = mapped_column(Integer)
    goal_value: Mapped[Decimal] = mapped_column(Numeric(18, 6))

    kpi: Mapped[Kpi] = relationship()
    employee: Mapped[HrEmployee] = relationship()
