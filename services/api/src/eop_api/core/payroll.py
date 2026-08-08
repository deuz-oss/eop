from enum import StrEnum


class PayrollRunStatus(StrEnum):
    """Single source of truth for `PayrollRun`'s lifecycle state.

    Per `docs/architecture/capabilities/payroll/decision.md` Addendum (Version
    2) §1: `DRAFT -> PROCESSING -> COMPLETED`, no `CANCELLED`. Mirrors
    `EventType`/`EventSource` (`core/attendance.py`): a fixed, closed
    enumeration owned by the application, not the generic
    `pending`/`approved`/`rejected` string convention `ApprovalService`
    coordinates across `LeaveRequest`/`OvertimeRequest`/`Timesheet` -- this is
    a different, payroll-computation-specific state machine with no shared
    workflow across entities.
    """

    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
