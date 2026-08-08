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


class PayslipLineItemType(StrEnum):
    """Single source of truth for `PayslipLineItem.component_type`.

    Advanced Payroll (`docs/architecture/capabilities/payroll-calculation/
    implementation-plan.md` §3.1, E1 -- structured calculation result).
    `BASE_SALARY`/`ALLOWANCE`/`OVERTIME` are earning-typed; the remaining
    four are deduction-typed. `PayrollCalculationService` derives
    earning/deduction classification from this enum, never from the sign
    of `line_amount` -- `line_amount` is always stored unsigned.
    """

    BASE_SALARY = "BASE_SALARY"
    ALLOWANCE = "ALLOWANCE"
    OVERTIME = "OVERTIME"
    ATTENDANCE_DEDUCTION = "ATTENDANCE_DEDUCTION"
    LEAVE_DEDUCTION = "LEAVE_DEDUCTION"
    STATUTORY_DEDUCTION = "STATUTORY_DEDUCTION"
    NON_STATUTORY_DEDUCTION = "NON_STATUTORY_DEDUCTION"


EARNING_LINE_ITEM_TYPES = frozenset(
    {PayslipLineItemType.BASE_SALARY, PayslipLineItemType.ALLOWANCE, PayslipLineItemType.OVERTIME}
)
DEDUCTION_LINE_ITEM_TYPES = frozenset(
    {
        PayslipLineItemType.ATTENDANCE_DEDUCTION,
        PayslipLineItemType.LEAVE_DEDUCTION,
        PayslipLineItemType.STATUTORY_DEDUCTION,
        PayslipLineItemType.NON_STATUTORY_DEDUCTION,
    }
)
