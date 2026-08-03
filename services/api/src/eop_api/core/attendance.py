from enum import StrEnum


class EventType(StrEnum):
    """Single source of truth for the kind of clock action an AttendanceEvent records."""

    CLOCK_IN = "CLOCK_IN"
    CLOCK_OUT = "CLOCK_OUT"
    BREAK_IN = "BREAK_IN"
    BREAK_OUT = "BREAK_OUT"


class EventSource(StrEnum):
    """Single source of truth for how an AttendanceEvent was captured."""

    SYSTEM = "SYSTEM"
    MANUAL = "MANUAL"
    IMPORT = "IMPORT"
