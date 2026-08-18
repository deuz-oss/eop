import uuid
from collections.abc import Callable, Sequence
from datetime import datetime
from typing import Any

from eop_api.core.payroll import PayrollRunStatus
from eop_api.models.attendance_event import AttendanceEvent
from eop_api.repositories.attendance_event import AttendanceEventRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.payroll_run import PayrollRunRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.schemas.attendance_event import (
    AttendanceEventCorrectionRequest,
    AttendanceEventCreate,
    AttendanceEventUpdate,
)
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.attendance_authorization import AttendanceAuthorizationEvaluator
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by an AttendanceEvent does not exist."""


class ShiftNotFoundError(Exception):
    """Raised when the shift referenced by an AttendanceEvent does not exist."""


class AttendanceAuthorizationDeniedError(Exception):
    """Raised when the Attendance Authorization Policy (Owner Only,
    `docs/architecture/capabilities/attendance-authorization/decision.md`) denies
    a create/get/update/delete/correct call -- i.e. `AuthorizationDecision.allowed`
    is `False`.

    Thrown only by `AttendanceEventService`, never by
    `AttendanceAuthorizationEvaluator` or `AuthorizationService` themselves.
    """


class AttendanceEventLockedError(Exception):
    """Raised when `create`/`correct`/`update`/`delete` is attempted for an
    `AttendanceEvent` date that falls within a `PayrollRun` period that has
    progressed beyond `DRAFT` (AttendanceEvent Integrity workstream).

    Once a payroll run covering a date starts `PROCESSING` (or is
    `COMPLETED`), that date is locked: no new event may be created for it,
    and no correction, update, or delete of an existing event on it is
    permitted, regardless of ownership. Locking `create` too closes the gap
    a create-only exploit would otherwise leave: without it, an employee
    could still retroactively insert a brand-new, favorable event for an
    already-processed date even though every other write path was locked.
    `PayrollRunRepository.find_covering_date` (persistence-only) supplies
    the candidate rows; this service decides what `status` means for the
    lock.
    """


class AttendanceEventDeletionNotAllowedError(Exception):
    """Raised on any `delete` of an existing `AttendanceEvent`
    (AttendanceEvent Integrity workstream): historical attendance events
    must not be destructively deleted. An event that needs to be corrected
    should be corrected via `AttendanceEventService.correct`, which leaves
    the original row intact and auditable; there is no scenario in which
    destroying a historical attendance fact is the right operation, so this
    is unconditional, not state-dependent.
    """


class AttendanceEventService:
    """Business logic for `AttendanceEvent`. Owns the transaction boundary via a UoW.

    `AttendanceEvent` is a single clock transaction (clock-in/out, break-in/out)
    -- not an employee-day summary, timesheet, or payroll record. Only the
    existence of `employee_id` and `shift_id` is validated on `create`.
    Sequencing (e.g. rejecting a clock-out before a clock-in) and
    duplicate-event detection are explicitly out of scope for this module
    and belong to future business-workflow PRs.

    AttendanceEvent Integrity workstream: a historical attendance event is
    never mutated or destructively deleted in place -- `event_time`,
    `event_type`, `source`, `remarks`, and `employee_id` are absent from
    `AttendanceEventUpdate` (only `shift_id` remains generic-CRUD-writable);
    correcting a historical field goes through `correct()` only, which
    creates a new event referencing the original via `corrects_id` and never
    touches the original row. `delete()` unconditionally rejects for any
    existing event -- there is no soft-delete and no state in which
    destroying a historical fact is the right operation. Once a `PayrollRun`
    covering a date progresses beyond `DRAFT`, that date is locked:
    `create`/`correct`/`update`/`delete` all reject via
    `AttendanceEventLockedError`, checked by `_reject_if_locked` against
    `PayrollRunRepository.find_covering_date` -- `create` is locked too, so
    a new, favorable event cannot be backdated into an already-processed
    period even though every other write path is closed. This module does
    not implement, and this decision
    does not require, manager/second-party approval, a permission model, or
    an organization hierarchy -- Owner Only authorization remains the
    baseline for every operation, including `correct`.

    Every `create`/`get`/`update`/`delete`/`correct` call is gated by the
    Attendance Authorization Policy (Owner Only): authorization is delegated
    to `AuthorizationService`/`AttendanceAuthorizationEvaluator` via
    `_authorize`, and a denied decision raises
    `AttendanceAuthorizationDeniedError`. This service never evaluates the
    policy itself -- see `_authorize`. `list`/`list_paginated` are scoped to
    the caller's own `employee_id` rather than authorized per-item, since
    there is no single resource to evaluate a decision against.

    Returned entities are expunged from the unit-of-work's session before it
    closes: the UoW always rolls back (and thus expires all attributes) on
    exit, so callers holding on to the entity after this method returns would
    otherwise hit a `DetachedInstanceError` on first attribute access.

    `update` additionally refreshes the entity before expunging it: `updated_at`
    is a server-side `onupdate`, and SQLAlchemy does not eagerly fetch it back
    via RETURNING after a plain UPDATE flush the way it does for INSERT, so it
    would otherwise be left expired -- refreshing while still attached avoids a
    `MissingGreenlet` (the ORM's lazy-load-on-attribute-access is not awaitable
    once the session has exited its async context).
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(
        self, data: AttendanceEventCreate, request_context: RequestContext
    ) -> AttendanceEvent:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if not await ShiftRepository(uow.session).exists(data.shift_id):
                raise ShiftNotFoundError(str(data.shift_id))

            await self._authorize(data, request_context)
            await self._reject_if_locked(uow, data.event_time)

            event = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(event)
            return event

    async def get(
        self, event_id: uuid.UUID, request_context: RequestContext
    ) -> AttendanceEvent | None:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is None:
                return None
            await self._authorize(event, request_context)
            uow.session.expunge(event)
            return event

    async def list(self, request_context: RequestContext) -> Sequence[AttendanceEvent]:
        """Attendance events owned by the caller's own `employee_id`.

        Filtered in-memory rather than via `AttendanceEventRepository.paginate`'s
        repository-level filtering: this method's underlying
        `BaseRepository.list()` has no filter parameter, and the repository
        is out of scope for this capability.
        """
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            events = await repo.list()
            current_employee_id = request_context.employee_context.employee.id
            owned = [event for event in events if event.employee_id == current_employee_id]
            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self,
        request_context: RequestContext,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[AttendanceEvent]:
        """Attendance events owned by the caller's own `employee_id`, paginated.

        `employee_id` is forced to the caller's own resolved employee id via
        repository-level filtering (`AttendanceEventRepository.paginate`'s
        existing `employee_id` filter), overriding any client-supplied value
        in `filters` -- the caller cannot widen the scope by passing a
        different `employee_id`.
        """
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            scoped_values = dict(filters.values) if filters else {}
            scoped_values["employee_id"] = request_context.employee_context.employee.id
            scoped_filters = FilterParams(values=scoped_values)
            page = await repo.paginate(
                offset=pagination.offset,
                limit=pagination.limit,
                search=search,
                filters=scoped_filters,
            )
            uow.session.expunge_all()
            return page

    async def update(
        self,
        event_id: uuid.UUID,
        data: AttendanceEventUpdate,
        request_context: RequestContext,
    ) -> AttendanceEvent | None:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is None:
                return None

            await self._authorize(event, request_context)
            await self._reject_if_locked(uow, event.event_time)

            values = data.model_dump(exclude_unset=True)

            if "shift_id" in values:
                if not await ShiftRepository(uow.session).exists(values["shift_id"]):
                    raise ShiftNotFoundError(str(values["shift_id"]))

            updated = await repo.update(event_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def correct(
        self,
        event_id: uuid.UUID,
        data: AttendanceEventCorrectionRequest,
        request_context: RequestContext,
    ) -> AttendanceEvent | None:
        """Creates a new `AttendanceEvent` correcting `event_id`, leaving the
        original row untouched. Any field omitted from `data` is carried
        over unchanged from the original; `employee_id`/`shift_id` always
        come from the original -- never from `data`, which has no such
        fields -- so a correction can never target a different employee or
        shift than the event it corrects.

        Returns `None` if `event_id` doesn't exist (mirrors `update`/
        `delete`'s existing not-found convention). A correction chain
        (correcting a correction) is permitted -- `corrects_id` must
        reference an already-persisted row and is never itself updatable,
        so no cycle can form regardless of chain depth; see
        `test_correct_chain_does_not_create_a_cycle`.
        """
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            original = await repo.get(event_id)
            if original is None:
                return None

            await self._authorize(original, request_context)
            await self._reject_if_locked(uow, original.event_time)

            values = data.model_dump(exclude_unset=True)
            correction = await repo.create(
                employee_id=original.employee_id,
                shift_id=original.shift_id,
                event_type=values.get("event_type", original.event_type),
                event_time=values.get("event_time", original.event_time),
                source=values.get("source", original.source),
                remarks=values.get("remarks", original.remarks),
                corrects_id=original.id,
            )
            await uow.commit()
            uow.session.expunge(correction)
            return correction

    async def delete(self, event_id: uuid.UUID, request_context: RequestContext) -> bool:
        """Never deletes. Returns `False` if `event_id` doesn't exist
        (mirrors every other service's not-found convention); raises
        `AttendanceEventDeletionNotAllowedError` if it does -- historical
        attendance events are corrected via `correct()`, never destroyed.
        """
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is None:
                return False

            await self._authorize(event, request_context)

            raise AttendanceEventDeletionNotAllowedError(str(event_id))

    async def _reject_if_locked(self, uow: SQLAlchemyUnitOfWork, event_time: datetime) -> None:
        """Raises `AttendanceEventLockedError` if any `PayrollRun` covering
        `event_time`'s date has progressed beyond `DRAFT`.

        `event_time` is UTC-normalized (`AttendanceEvent.event_time` is
        `DateTime(timezone=True)`); taking `.date()` of it is the same UTC
        calendar-day interpretation the ratified Reconciliation Timezone
        Decision (`docs/architecture/ATTENDANCE_RECONCILIATION_DESIGN.md`)
        uses -- this reuses that decision rather than introducing a second,
        competing day-boundary interpretation.
        """
        covering = await PayrollRunRepository(uow.session).find_covering_date(event_time.date())
        if any(run.status != PayrollRunStatus.DRAFT for run in covering):
            raise AttendanceEventLockedError(str(event_time.date()))

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Attendance Authorization Policy (Owner Only) for `resource`.

        `resource` is the `AttendanceEventCreate` payload for `create`, or the
        already-loaded `AttendanceEvent` for `get`/`update`/`delete`. This
        method only delegates to `AuthorizationService`/
        `AttendanceAuthorizationEvaluator`; it contains no comparison of its
        own, so `AttendanceEventService` never evaluates authorization itself.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(AttendanceAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise AttendanceAuthorizationDeniedError(
                decision.reason or "Attendance authorization denied"
            )
