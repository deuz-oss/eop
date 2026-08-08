from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity
from eop_api.db.mixins import EffectiveDatingMixin


class WorkSchedule(BaseEntity, EffectiveDatingMixin):
    """One employee's weekly working-day pattern, effective-dated (multiple
    rows per employee).

    `docs/architecture/capabilities/work-schedule/iteration-1-implementation-plan.md`
    §1 #1/#3: Work Schedule is its own Aggregate Root. Recurrence (which days
    of the week are worked) is modelled as plain content -- seven boolean
    columns on this one effective-dated row -- not as a template/instance
    mechanism; no recurring-row-generation infrastructure exists or is
    needed. Effective dating (when a given weekly pattern applies) is the
    already-accepted `EffectiveDatingMixin` mechanism, unmodified.

    Mirrors `Compensation`'s shape directly (`models/compensation.py`):
    employee-scoped, multi-row-per-employee, no uniqueness constraint on
    `employee_id`, `is_active` independent of temporal validity, `corrects_id`
    for compensating correction. Overlap is scoped to `employee_id` alone
    (an employee has one working-pattern state at a time), matching
    `Compensation`'s own scope rather than `Allowance`'s type-scoped variant.

    `shift_id` is the shift worked on this pattern's working days --
    Work Schedule depends on/consumes `Shift`, never owns or extends it
    (`work-schedule/decision.md` §2).

    No relationship to Shift Assignment, Attendance, or Payroll Calculation
    exists on this entity -- explicitly deferred
    (`iteration-1-implementation-plan.md` §1 #2, #6, #7, §10).
    """

    __tablename__ = "work_schedules"
    __table_args__ = (
        Index("ix_work_schedules_employee_effective", "employee_id", "effective_from"),
        Index("ix_work_schedules_corrects_id", "corrects_id"),
        Index("ix_work_schedules_shift_id", "shift_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="RESTRICT"),
    )
    works_monday: Mapped[bool] = mapped_column(Boolean, default=False)
    works_tuesday: Mapped[bool] = mapped_column(Boolean, default=False)
    works_wednesday: Mapped[bool] = mapped_column(Boolean, default=False)
    works_thursday: Mapped[bool] = mapped_column(Boolean, default=False)
    works_friday: Mapped[bool] = mapped_column(Boolean, default=False)
    works_saturday: Mapped[bool] = mapped_column(Boolean, default=False)
    works_sunday: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    corrects_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("work_schedules.id", ondelete="RESTRICT"), default=None
    )
