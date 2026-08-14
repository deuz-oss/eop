import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.models.leave_request import LeaveRequest
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.leave_request import LeaveRequestRepository
from eop_api.schemas.leave_request import LeaveRequestCreate, LeaveRequestUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.services.leave_authorization import LeaveAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a LeaveRequest does not exist."""


class InvalidLeaveDateRangeError(Exception):
    """Raised when a LeaveRequest's `end_date` is earlier than its `start_date`."""


class LeaveAuthorizationDeniedError(Exception):
    """Raised when the Leave Authorization Policy (Owner Only,
    `docs/architecture/capabilities/leave-authorization/decision.md`) denies
    a create/get/update/delete call -- i.e. `AuthorizationDecision.allowed`
    is `False`.

    Thrown only by `LeaveRequestService`, never by `LeaveAuthorizationEvaluator`
    or `AuthorizationService` themselves.
    """


class LeaveRequestService:
    """Business logic for `LeaveRequest`. Owns the transaction boundary via a UoW.

    `LeaveRequest` is a single employee's request for a dated span -- not a
    balance or entitlement record. Only the existence of `employee_id` and
    `start_date <= end_date` are validated on `create`/`update`. `status`,
    `approved_by`, `approved_at`, and `rejection_reason` are storage-only
    columns here -- no transition validation, audit logging, or
    event/notification dispatch is performed by this service. Which
    component orchestrates an approval decision is an intentionally
    unresolved architectural question (per
    `docs/architecture/APPROVAL_WORKFLOW_DESIGN.md` §10) and is deferred to a
    future PR, not decided here.

    Every `create`/`get`/`update`/`delete` call is gated by the Leave
    Authorization Policy (Owner Only): authorization is delegated to
    `AuthorizationService`/`LeaveAuthorizationEvaluator` via `_authorize`,
    and a denied decision raises `LeaveAuthorizationDeniedError`. This
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
        self, data: LeaveRequestCreate, request_context: RequestContext
    ) -> LeaveRequest:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            await self._authorize(data, request_context)

            if data.end_date < data.start_date:
                raise InvalidLeaveDateRangeError(
                    f"end_date {data.end_date} is before start_date {data.start_date}"
                )

            leave_request = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(leave_request)
            return leave_request

    async def get(
        self, leave_request_id: uuid.UUID, request_context: RequestContext
    ) -> LeaveRequest | None:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            leave_request = await repo.get(leave_request_id)
            if leave_request is None:
                return None
            await self._authorize(leave_request, request_context)
            uow.session.expunge(leave_request)
            return leave_request

    async def list(self, request_context: RequestContext) -> Sequence[LeaveRequest]:
        """Leave requests owned by the caller's own `employee_id`.

        Filtered in-memory rather than via `LeaveRequestRepository.paginate`'s
        repository-level filtering: this method's underlying
        `BaseRepository.list()` has no filter parameter, and the repository
        is out of scope for this capability.
        """
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            leave_requests = await repo.list()
            current_employee_id = request_context.employee_context.employee.id
            owned = [lr for lr in leave_requests if lr.employee_id == current_employee_id]
            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self,
        request_context: RequestContext,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[LeaveRequest]:
        """Leave requests owned by the caller's own `employee_id`, paginated.

        `employee_id` is forced to the caller's own resolved employee id via
        repository-level filtering (`LeaveRequestRepository.paginate`'s
        existing `employee_id` filter), overriding any client-supplied value
        in `filters` -- the caller cannot widen the scope by passing a
        different `employee_id`.
        """
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
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
        leave_request_id: uuid.UUID,
        data: LeaveRequestUpdate,
        request_context: RequestContext,
    ) -> LeaveRequest | None:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            leave_request = await repo.get(leave_request_id)
            if leave_request is None:
                return None

            await self._authorize(leave_request, request_context)

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            start_date = values.get("start_date", leave_request.start_date)
            end_date = values.get("end_date", leave_request.end_date)

            if end_date < start_date:
                raise InvalidLeaveDateRangeError(
                    f"end_date {end_date} is before start_date {start_date}"
                )

            updated = await repo.update(leave_request_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, leave_request_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            leave_request = await repo.get(leave_request_id)
            if leave_request is None:
                return False

            await self._authorize(leave_request, request_context)

            deleted = await repo.delete(leave_request_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Leave Authorization Policy (Owner Only) for `resource`.

        `resource` is the `LeaveRequestCreate` payload for `create`, or the
        already-loaded `LeaveRequest` for `get`/`update`/`delete`. This
        method only delegates to `AuthorizationService`/
        `LeaveAuthorizationEvaluator`; it contains no comparison of its own,
        so `LeaveRequestService` never evaluates authorization itself.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(LeaveAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise LeaveAuthorizationDeniedError(decision.reason or "Leave authorization denied")
