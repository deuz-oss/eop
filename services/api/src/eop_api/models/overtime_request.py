from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class OvertimeRequest(BaseEntity):
    """A single employee's request for overtime on one date.

    Deliberately request-shaped, not calculation/payroll shaped: each row is
    one ask, covering one date's start/end time window, for one HrEmployee.
    Attendance reconciliation, overtime-hours calculation, and payroll
    integration are all future concerns -- out of scope here.

    `employee_id` is `ON DELETE RESTRICT`, matching every other FK into
    `HrEmployee` from HR data: overtime history must be preserved, not
    silently cascaded away.

    `status` is intentionally a plain string column, storage only -- the same
    style already used by `LeaveRequest.status`. No enum, no CHECK
    constraint: transition validation (`pending` -> `approved`/`rejected`) is
    enforced by `OvertimeRequestService.approve`/`.reject`, not by the
    database.

    `approved_by`/`approved_at`/`rejection_reason` are populated only by
    `OvertimeRequestService.approve`/`.reject`, per
    `docs/architecture/APPROVAL_WORKFLOW_DESIGN.md`. `approved_by` is
    `ON DELETE RESTRICT` against `users.id`, matching the retention posture of
    every other FK on this entity.
    """

    __tablename__ = "overtime_requests"
    __table_args__ = (
        Index("ix_overtime_requests_employee_id", "employee_id"),
        Index("ix_overtime_requests_overtime_date", "overtime_date"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    overtime_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    # Transition validation lives in OvertimeRequestService.approve/.reject, not here.
    status: Mapped[str] = mapped_column(String(50), default="pending")
    reason: Mapped[str | None] = mapped_column(String(2000), default=None)

    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), default=None
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), default=None)
