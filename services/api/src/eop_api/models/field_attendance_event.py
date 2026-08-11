from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, Numeric
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.core.field_attendance import FieldAttendanceEventType
from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.file_object import FileObject
    from eop_api.models.hr_employee import HrEmployee


class FieldAttendanceEvent(BaseEntity):
    """A single field attendance event (check-in/check-out) for an
    HrEmployee, evidenced by GPS coordinates and a mandatory selfie.

    Standalone aggregate, deliberately separate from the HR/Payroll
    `AttendanceEvent` (shift clock-in/out feeding Payroll's attendance
    deduction) despite the shared word "Attendance" -- neither reused nor
    modified (`docs/architecture/capabilities/field-attendance/
    field-attendance-iteration-1-scope-and-implementation-plan.md` §2). No
    relationship to `Visit`, `Store`, `Mission`, or any Territory/Region/Area
    concept -- represents field-presence evidence, independent of any
    particular Visit.

    Event-shaped, not employee-day shaped: each row is one check-in or
    check-out at one point in time (§3/§4). No uniqueness constraint --
    multiple events per employee per day are allowed, and no automatic
    pairing/sequencing/correction logic exists, mirroring `AttendanceEvent`'s
    own established precedent.

    `latitude`/`longitude` mirror `Store.latitude`/`Store.longitude`'s exact
    `Numeric(9, 6)` precedent, but are required here (not nullable) --
    GPS is mandatory for Iteration 1 (§5). `gps_accuracy_meters` is stored
    as device-reported evidence only; no rejection threshold is enforced at
    this layer (structural range validation only, in `FieldAttendanceEventService`).

    `selfie_file_id` is a mandatory (`NOT NULL`) FK to the existing
    `FileObject`, reused unmodified -- no new file-storage subsystem, no
    biometric processing. `ON DELETE RESTRICT`, matching every other
    mandatory FK in this codebase: history/evidence must be preserved, not
    silently cascaded away (§11's rationale).

    `employee_id` is `ON DELETE RESTRICT`, matching every other FK into
    `HrEmployee` from field-execution/HR data.
    """

    __tablename__ = "field_attendance_events"
    __table_args__ = (
        Index("ix_field_attendance_events_employee_id", "employee_id"),
        Index("ix_field_attendance_events_event_type", "event_type"),
        Index("ix_field_attendance_events_event_time", "event_time"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    event_type: Mapped[FieldAttendanceEventType] = mapped_column(
        SqlEnum(
            FieldAttendanceEventType,
            name="field_attendance_event_type",
            native_enum=False,
            length=20,
        ),
    )
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    latitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal] = mapped_column(Numeric(9, 6))
    gps_accuracy_meters: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    selfie_file_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT"),
    )

    employee: Mapped[HrEmployee] = relationship()
    selfie_file: Mapped[FileObject] = relationship()
