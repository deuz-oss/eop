from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Timesheet(BaseEntity):
    """A single employee's submitted timesheet covering a dated span.

    Deliberately submission-shaped, not calculation/projection shaped: each
    row is one ask, covering one contiguous date span, for one HrEmployee.
    Attendance/overtime/leave/holiday reconciliation, computed hour totals,
    and payroll integration are all future concerns -- out of scope here
    (per `docs/architecture/TIMESHEET_DESIGN.md`).

    `employee_id` is `ON DELETE RESTRICT`, matching every other FK into
    `HrEmployee` from HR data: timesheet history must be preserved, not
    silently cascaded away.

    `status` is intentionally a plain string column, storage only -- the
    same style already used by `LeaveRequest.status`/`OvertimeRequest.status`.
    No enum, no CHECK constraint: transition validation (`pending` ->
    `approved`/`rejected`) is enforced by `TimesheetService.approve`/
    `.reject`, not by the database.

    `approved_by`/`approved_at`/`rejection_reason` are populated only by
    `TimesheetService.approve`/`.reject`, per
    `docs/architecture/APPROVAL_WORKFLOW_DESIGN.md`. `approved_by` is
    `ON DELETE RESTRICT` against `users.id`, matching the retention posture of
    every other FK on this entity.
    """

    __tablename__ = "timesheets"
    __table_args__ = (
        Index("ix_timesheets_employee_id", "employee_id"),
        Index("ix_timesheets_start_date", "start_date"),
        Index("ix_timesheets_end_date", "end_date"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    # Transition validation lives in TimesheetService.approve/.reject, not here.
    status: Mapped[str] = mapped_column(String(50), default="pending")

    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), default=None
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), default=None)
