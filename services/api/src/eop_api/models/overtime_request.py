from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import Date, ForeignKey, Index, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class OvertimeRequest(BaseEntity):
    """A single employee's request for overtime on one date.

    Deliberately request-shaped, not calculation/approval/payroll shaped: each
    row is one ask, covering one date's start/end time window, for one
    HrEmployee. Attendance reconciliation, overtime-hours calculation,
    approval workflow, and payroll integration are all future concerns --
    out of scope here.

    `employee_id` is `ON DELETE RESTRICT`, matching every other FK into
    `HrEmployee` from HR data: overtime history must be preserved, not
    silently cascaded away.

    `status` is intentionally a plain string column, storage only -- the same
    style already used by `LeaveRequest.status`. No enum, no CHECK
    constraint, no transition validation: approval workflow is a future PR's
    concern, not this one's.
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
    # Storage only -- no transition validation. Approval workflow is intentionally
    # deferred to a future PR.
    status: Mapped[str] = mapped_column(String(50), default="pending")
    reason: Mapped[str | None] = mapped_column(String(2000), default=None)
