import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.models.attendance_event import AttendanceEvent
from eop_api.repositories.attendance_event import AttendanceEventRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.schemas.attendance_event import AttendanceEventCreate, AttendanceEventUpdate
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
    a create/get/update/delete call -- i.e. `AuthorizationDecision.allowed`
    is `False`.

    Thrown only by `AttendanceEventService`, never by
    `AttendanceAuthorizationEvaluator` or `AuthorizationService` themselves.
    """


class AttendanceEventService:
    """Business logic for `AttendanceEvent`. Owns the transaction boundary via a UoW.

    `AttendanceEvent` is a single clock transaction (clock-in/out, break-in/out)
    -- not an employee-day summary, timesheet, or payroll record. Only the
    existence of `employee_id` and `shift_id` is validated here. Sequencing
    (e.g. rejecting a clock-out before a clock-in), duplicate-event detection,
    and shift-matching are explicitly out of scope for this module and belong
    to future business-workflow PRs.

    Every `create`/`get`/`update`/`delete` call is gated by the Attendance
    Authorization Policy (Owner Only): authorization is delegated to
    `AuthorizationService`/`AttendanceAuthorizationEvaluator` via `_authorize`,
    and a denied decision raises `AttendanceAuthorizationDeniedError`. This
    service never evaluates the policy itself -- see `_authorize`. `list`/
    `list_paginated` are scoped to the caller's own `employee_id` rather
    than authorized per-item, since there is no single resource to evaluate
    a decision against.

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

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            if "shift_id" in values:
                if not await ShiftRepository(uow.session).exists(values["shift_id"]):
                    raise ShiftNotFoundError(str(values["shift_id"]))

            updated = await repo.update(event_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, event_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is None:
                return False

            await self._authorize(event, request_context)

            deleted = await repo.delete(event_id)
            if deleted:
                await uow.commit()
            return deleted

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
