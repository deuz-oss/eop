import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.models.field_attendance_event import FieldAttendanceEvent
from eop_api.repositories.field_attendance_event import FieldAttendanceEventRepository
from eop_api.repositories.file import FileRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.schemas.field_attendance_event import (
    FieldAttendanceEventCreate,
    FieldAttendanceEventUpdate,
)
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.attendance_authorization import AttendanceAuthorizationEvaluator
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a FieldAttendanceEvent does not exist."""


class SelfieFileNotFoundError(Exception):
    """Raised when the FileObject referenced by `selfie_file_id` does not exist."""


class FieldAttendanceAuthorizationDeniedError(Exception):
    """Raised when the Attendance Authorization Policy (Owner Only,
    `docs/architecture/capabilities/attendance-authorization/decision.md`)
    denies a create/get/update/delete call -- i.e. `AuthorizationDecision.
    allowed` is `False`.

    Thrown only by `FieldAttendanceEventService`, never by
    `AttendanceAuthorizationEvaluator` or `AuthorizationService` themselves.
    """


class FieldAttendanceEventService:
    """Business logic for `FieldAttendanceEvent`. Owns the transaction
    boundary via a UoW.

    `FieldAttendanceEvent` is a standalone aggregate, deliberately separate
    from the HR/Payroll `AttendanceEvent` (`docs/architecture/capabilities/
    field-attendance/field-attendance-iteration-1-scope-and-implementation-
    plan.md` §2) -- neither reuses nor modifies it. Only the existence of
    `employee_id` and `selfie_file_id` is validated here. Sequencing (e.g.
    rejecting a check-out before a check-in), duplicate-event detection, and
    GPS/accuracy business-threshold rejection are explicitly out of scope
    for this module (§4/§5) -- only structural GPS range validation is
    enforced, at the schema layer (`FieldAttendanceEventCreate`).

    Every `create`/`get`/`update`/`delete` call is gated by the Attendance
    Authorization Policy (Owner Only): authorization is delegated to
    `AuthorizationService`/`AttendanceAuthorizationEvaluator` -- reused
    completely unmodified from the sibling HR `AttendanceEvent` capability,
    since it only ever inspects `resource.employee_id` and does not
    reference the `AttendanceEvent` model by type (§7) -- via `_authorize`,
    and a denied decision raises `FieldAttendanceAuthorizationDeniedError`.
    This service never evaluates the policy itself -- see `_authorize`.
    `list`/`list_paginated` are scoped to the caller's own `employee_id`
    rather than authorized per-item, mirroring `AttendanceEventService`
    exactly -- there is no single resource to evaluate a decision against
    for a collection read.

    Returned entities are expunged from the unit-of-work's session before it
    closes: the UoW always rolls back (and thus expires all attributes) on
    exit, so callers holding on to the entity after this method returns would
    otherwise hit a `DetachedInstanceError` on first attribute access.

    `update` additionally refreshes the entity before expunging it, for the
    same server-side `onupdate` reason documented on `AttendanceEventService.
    update`.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(
        self, data: FieldAttendanceEventCreate, request_context: RequestContext
    ) -> FieldAttendanceEvent:
        async with self._uow_factory() as uow:
            repo = FieldAttendanceEventRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if not await FileRepository(uow.session).exists(data.selfie_file_id):
                raise SelfieFileNotFoundError(str(data.selfie_file_id))

            await self._authorize(data, request_context)

            event = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(event)
            return event

    async def get(
        self, event_id: uuid.UUID, request_context: RequestContext
    ) -> FieldAttendanceEvent | None:
        async with self._uow_factory() as uow:
            repo = FieldAttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is None:
                return None
            await self._authorize(event, request_context)
            uow.session.expunge(event)
            return event

    async def list(self, request_context: RequestContext) -> Sequence[FieldAttendanceEvent]:
        """Field attendance events owned by the caller's own `employee_id`.

        Filtered in-memory, mirroring `AttendanceEventService.list` exactly
        -- `BaseRepository.list()` has no filter parameter, and the
        repository is out of scope for this capability.
        """
        async with self._uow_factory() as uow:
            repo = FieldAttendanceEventRepository(uow.session)
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
    ) -> Page[FieldAttendanceEvent]:
        """Field attendance events owned by the caller's own `employee_id`, paginated.

        `employee_id` is forced to the caller's own resolved employee id via
        repository-level filtering (`FieldAttendanceEventRepository.
        paginate`'s existing `employee_id` filter), overriding any
        client-supplied value in `filters` -- mirrors `AttendanceEventService.
        list_paginated` exactly; the caller cannot widen the scope by
        passing a different `employee_id`.
        """
        async with self._uow_factory() as uow:
            repo = FieldAttendanceEventRepository(uow.session)
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
        data: FieldAttendanceEventUpdate,
        request_context: RequestContext,
    ) -> FieldAttendanceEvent | None:
        async with self._uow_factory() as uow:
            repo = FieldAttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is None:
                return None

            await self._authorize(event, request_context)

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            if "selfie_file_id" in values:
                if not await FileRepository(uow.session).exists(values["selfie_file_id"]):
                    raise SelfieFileNotFoundError(str(values["selfie_file_id"]))

            updated = await repo.update(event_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, event_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = FieldAttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is None:
                return False

            await self._authorize(event, request_context)

            deleted = await repo.delete(event_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Attendance Authorization Policy (Owner Only) against
        `resource`. `AttendanceAuthorizationEvaluator` is reused completely
        unmodified from the sibling HR `AttendanceEvent` capability: it only
        ever inspects `resource.employee_id`, so passing a
        `FieldAttendanceEvent`/`FieldAttendanceEventCreate` is sufficient
        and requires no new evaluator class (§7).
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(AttendanceAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise FieldAttendanceAuthorizationDeniedError(
                decision.reason or "Field attendance authorization denied"
            )
