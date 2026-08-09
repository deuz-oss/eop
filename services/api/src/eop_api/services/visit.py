import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.models.visit import Visit
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.store import StoreRepository
from eop_api.repositories.visit import VisitRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.schemas.visit import VisitCreate, VisitUpdate
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.services.visit_authorization import VisitAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Visit does not exist."""


class StoreNotFoundError(Exception):
    """Raised when the store referenced by a Visit does not exist."""


class VisitAuthorizationDeniedError(Exception):
    """Raised when the Visit Authorization Policy (Owner Only,
    `docs/architecture/capabilities/visit/
    iteration-1-scope-and-implementation-plan.md` §4) denies a
    create/get/update/delete call -- i.e. `AuthorizationDecision.allowed`
    is `False`.

    Thrown only by `VisitService`, never by `VisitAuthorizationEvaluator`
    or `AuthorizationService` themselves.
    """


class VisitService:
    """Business logic for `Visit`. Owns the transaction boundary via a UoW.

    `Visit` is a single field-employee-to-store visit record -- not a
    Mission, timesheet, or payroll record. Only the existence of
    `employee_id` and `store_id` is validated here. No status/lifecycle,
    no GPS/photo, no Survey/audit sub-records (`iteration-1-scope-and-
    implementation-plan.md` §2/§5/§7).

    Every `create`/`get`/`update`/`delete` call is gated by the Visit
    Authorization Policy (Owner Only): authorization is delegated to
    `AuthorizationService`/`VisitAuthorizationEvaluator` via `_authorize`,
    and a denied decision raises `VisitAuthorizationDeniedError`. This
    service never evaluates the policy itself -- see `_authorize`. `list`/
    `list_paginated` are scoped to the caller's own `employee_id` rather
    than authorized per-item, mirroring `AttendanceEventService` exactly.

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

    async def create(self, data: VisitCreate, request_context: RequestContext) -> Visit:
        async with self._uow_factory() as uow:
            repo = VisitRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if not await StoreRepository(uow.session).exists(data.store_id):
                raise StoreNotFoundError(str(data.store_id))

            await self._authorize(data, request_context)

            visit = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(visit)
            return visit

    async def get(self, visit_id: uuid.UUID, request_context: RequestContext) -> Visit | None:
        async with self._uow_factory() as uow:
            repo = VisitRepository(uow.session)
            visit = await repo.get(visit_id)
            if visit is None:
                return None
            await self._authorize(visit, request_context)
            uow.session.expunge(visit)
            return visit

    async def list(self, request_context: RequestContext) -> Sequence[Visit]:
        """Visits owned by the caller's own `employee_id`.

        Filtered in-memory rather than via `VisitRepository.paginate`'s
        repository-level filtering, mirroring `AttendanceEventService.list`
        exactly.
        """
        async with self._uow_factory() as uow:
            repo = VisitRepository(uow.session)
            visits = await repo.list()
            current_employee_id = request_context.employee_context.employee.id
            owned = [visit for visit in visits if visit.employee_id == current_employee_id]
            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self,
        request_context: RequestContext,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Visit]:
        """Visits owned by the caller's own `employee_id`, paginated.

        `employee_id` is forced to the caller's own resolved employee id via
        repository-level filtering, overriding any client-supplied value in
        `filters` -- mirrors `AttendanceEventService.list_paginated` exactly.
        """
        async with self._uow_factory() as uow:
            repo = VisitRepository(uow.session)
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
        visit_id: uuid.UUID,
        data: VisitUpdate,
        request_context: RequestContext,
    ) -> Visit | None:
        async with self._uow_factory() as uow:
            repo = VisitRepository(uow.session)
            visit = await repo.get(visit_id)
            if visit is None:
                return None

            await self._authorize(visit, request_context)

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            if "store_id" in values:
                if not await StoreRepository(uow.session).exists(values["store_id"]):
                    raise StoreNotFoundError(str(values["store_id"]))

            updated = await repo.update(visit_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, visit_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = VisitRepository(uow.session)
            visit = await repo.get(visit_id)
            if visit is None:
                return False

            await self._authorize(visit, request_context)

            deleted = await repo.delete(visit_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Visit Authorization Policy (Owner Only) for `resource`.

        `resource` is the `VisitCreate` payload for `create`, or the
        already-loaded `Visit` for `get`/`update`/`delete`. This method only
        delegates to `AuthorizationService`/`VisitAuthorizationEvaluator`; it
        contains no comparison of its own, so `VisitService` never evaluates
        authorization itself.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(VisitAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise VisitAuthorizationDeniedError(decision.reason or "Visit authorization denied")
