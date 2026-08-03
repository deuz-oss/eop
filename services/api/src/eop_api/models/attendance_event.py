from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.core.attendance import EventSource, EventType
from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.hr_employee import HrEmployee
    from eop_api.models.shift import Shift


class AttendanceEvent(BaseEntity):
    """A single attendance clock transaction (clock-in/out, break-in/out) for an HrEmployee.

    Deliberately event-shaped, not employee-day or summary shaped: each row is
    one clock action at one point in time. Employee-day rollups, timesheets,
    overtime, and payroll are all future projections built on top of this
    stream -- out of scope here. `event_type` and `source` are stored via
    `sa.Enum(..., native_enum=False)`, so they render as a plain `VARCHAR`
    column (no separate Postgres `CREATE TYPE`/`DROP TYPE` lifecycle to manage
    across migrations) while still round-tripping as `EventType`/`EventSource`
    on the Python side -- `EventType`/`EventSource` remain the single source
    of truth for valid values.

    Both `employee_id` and `shift_id` are `ON DELETE RESTRICT`, matching every
    other FK into `HrEmployee`/`Shift` from HR data: attendance history must
    be preserved, not silently cascaded away.
    """

    __tablename__ = "attendance_events"
    __table_args__ = (
        Index("ix_attendance_events_employee_id", "employee_id"),
        Index("ix_attendance_events_shift_id", "shift_id"),
        Index("ix_attendance_events_event_time", "event_time"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="RESTRICT"),
    )
    event_type: Mapped[EventType] = mapped_column(
        SqlEnum(EventType, name="attendance_event_type", native_enum=False, length=20),
    )
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[EventSource] = mapped_column(
        SqlEnum(EventSource, name="attendance_event_source", native_enum=False, length=20),
    )
    remarks: Mapped[str | None] = mapped_column(String(2000), default=None)

    employee: Mapped[HrEmployee] = relationship()
    shift: Mapped[Shift] = relationship()
