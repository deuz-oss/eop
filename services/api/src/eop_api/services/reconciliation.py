import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, time

from eop_api.repositories.attendance_event import AttendanceEventRepository
from eop_api.repositories.holiday import HolidayRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.leave_request import LeaveRequestRepository
from eop_api.schemas.reconciliation import AttendanceReconciliationResponse
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

APPROVED_STATUS = "approved"


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee being reconciled does not exist."""


class ReconciliationService:
    """Computes one employee's attendance result for one date.

    This is the repository's first read-oriented orchestration service, per
    `docs/architecture/ATTENDANCE_RECONCILIATION_DESIGN.md`. It owns no
    aggregate, no table, and no repository of its own. It follows
    `ApprovalService`'s DI/UnitOfWork/repository-coordination shape (a
    `uow_factory`-only constructor, one `uow` per call, repositories
    constructed against the shared `uow.session`) -- that shape is the only
    part of `ApprovalService` this service is a precedent-based extension of.
    `ApprovalService` never reads more than one repository per call and never
    combines results; this service reads four (`HrEmployeeRepository`,
    `HolidayRepository`, `LeaveRequestRepository`, `AttendanceEventRepository`)
    and resolves them into a single result -- that composition, and the
    precedence order below, is new, unprecedented behavior, not something
    `ApprovalService` establishes (design doc §1/§6).

    Read-only: no repository's `create`/`update`/`delete` is ever called, and
    `uow.commit()` is never called (design doc §8).

    Both repositories this service reads from are deliberately neutral:
    `LeaveRequestRepository.find_for_employee_on_date` returns matching rows
    regardless of `status`, and `AttendanceEventRepository.exists_between`
    takes an explicit `[start, end]` range with no day/timezone
    interpretation of its own. Filtering by `status == "approved"` and
    computing the day boundary passed to `exists_between` are both business/
    orchestration decisions performed here, in this service, not in either
    repository -- repositories must not encode approval-workflow semantics or
    calendar/timezone interpretation (design doc §5).

    v1 scope is deliberately narrow -- single employee, single date, exactly
    four rules, evaluated in order (design doc's implementation scope):

    1. The employee must exist, or `EmployeeNotFoundError` is raised.
    2. If `target_date` is a `Holiday` -> `"holiday"`.
    3. Else if an `approved` `LeaveRequest` covers `target_date` -> `"leave"`.
    4. Else if any `AttendanceEvent` falls on `target_date` -> `"present"`.
    5. Else -> `"absent"`.

    Overtime, lateness, early departure, grace periods, shift schedules,
    overnight-shift attribution, and timezone handling are explicitly out of
    scope for v1 -- see the design doc's still-open ambiguities (§12).
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def reconcile(
        self, employee_id: uuid.UUID, target_date: date
    ) -> AttendanceReconciliationResponse:
        async with self._uow_factory() as uow:
            if not await HrEmployeeRepository(uow.session).exists(employee_id):
                raise EmployeeNotFoundError(str(employee_id))

            holiday = await HolidayRepository(uow.session).get_by_holiday_date(target_date)
            if holiday is not None:
                return AttendanceReconciliationResponse(
                    employee_id=employee_id, date=target_date, status="holiday"
                )

            leave_requests = await LeaveRequestRepository(
                uow.session
            ).find_for_employee_on_date(employee_id, target_date)
            if any(request.status == APPROVED_STATUS for request in leave_requests):
                return AttendanceReconciliationResponse(
                    employee_id=employee_id, date=target_date, status="leave"
                )

            day_start, day_end = self._day_bounds(target_date)
            has_attendance = await AttendanceEventRepository(uow.session).exists_between(
                employee_id, day_start, day_end
            )
            if has_attendance:
                return AttendanceReconciliationResponse(
                    employee_id=employee_id, date=target_date, status="present"
                )

            return AttendanceReconciliationResponse(
                employee_id=employee_id, date=target_date, status="absent"
            )

    @staticmethod
    def _day_bounds(target_date: date) -> tuple[datetime, datetime]:
        """TEMPORARY placeholder day-boundary interpretation for `target_date`.

        Treats `target_date` as a UTC calendar day. This is **not** a
        resolution of the timezone-attribution ambiguity left open by
        `docs/architecture/ATTENDANCE_RECONCILIATION_DESIGN.md` §12.4 -- it is
        an arbitrary placeholder pending a product/architecture decision on
        which timezone (server UTC, the employee's `Location`, device-reported
        local time) should govern day-boundary attribution. Confined entirely
        to this orchestration service, per that document's §5 boundary: the
        repository layer performs no day/timezone interpretation of its own,
        and must not gain any until that ambiguity is actually resolved.
        """
        return (
            datetime.combine(target_date, time.min, tzinfo=UTC),
            datetime.combine(target_date, time.max, tzinfo=UTC),
        )
