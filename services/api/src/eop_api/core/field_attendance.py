from enum import StrEnum


class FieldAttendanceEventType(StrEnum):
    """Single source of truth for the kind of field attendance event a
    `FieldAttendanceEvent` records.

    Deliberately a separate enum from `core.attendance.EventType`
    (`CLOCK_IN`/`CLOCK_OUT`/`BREAK_IN`/`BREAK_OUT`) -- `FieldAttendanceEvent`
    is a standalone aggregate from the HR/Payroll `AttendanceEvent`, not an
    extension of it (`docs/architecture/capabilities/field-attendance/
    field-attendance-iteration-1-scope-and-implementation-plan.md` §2/§3).
    """

    CHECK_IN = "CHECK_IN"
    CHECK_OUT = "CHECK_OUT"
