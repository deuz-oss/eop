from enum import StrEnum


class ApplicationStatus(StrEnum):
    """Single source of truth for `Application`'s lifecycle state.

    Per `docs/architecture/capabilities/recruitment/
    iteration-2-business-decision-package.md` (Approved, D1 -- Standard
    Funnel): `applied -> screening -> interviewing -> offered -> hired`,
    with `rejected`/`withdrawn` reachable from any non-terminal stage.
    Forward-only -- no backward transitions. `hired`/`rejected`/`withdrawn`
    are terminal and cannot be reopened. Mirrors `PayrollRunStatus`
    (`core/payroll.py`): a fixed, closed enumeration owned by this
    application, not the generic `pending`/`approved`/`rejected` string
    convention `ApprovalService` coordinates across `LeaveRequest`/
    `OvertimeRequest`/`Timesheet` -- a different, Recruitment-specific
    state machine with no shared workflow across entities.
    """

    APPLIED = "applied"
    SCREENING = "screening"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


VALID_APPLICATION_TRANSITIONS: dict[ApplicationStatus, frozenset[ApplicationStatus]] = {
    ApplicationStatus.APPLIED: frozenset(
        {ApplicationStatus.SCREENING, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
    ),
    ApplicationStatus.SCREENING: frozenset(
        {ApplicationStatus.INTERVIEWING, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
    ),
    ApplicationStatus.INTERVIEWING: frozenset(
        {ApplicationStatus.OFFERED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
    ),
    ApplicationStatus.OFFERED: frozenset(
        {ApplicationStatus.HIRED, ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}
    ),
    ApplicationStatus.HIRED: frozenset(),
    ApplicationStatus.REJECTED: frozenset(),
    ApplicationStatus.WITHDRAWN: frozenset(),
}
"""Approved transition graph (D1). Every value is a `frozenset` -- `HIRED`/
`REJECTED`/`WITHDRAWN` map to the empty set, meaning no transition out of
a terminal state is ever valid, enforced by `ApplicationService.transition`.
"""
