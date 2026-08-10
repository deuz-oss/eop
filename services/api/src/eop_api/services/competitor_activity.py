import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.models.competitor_activity import CompetitorActivity
from eop_api.repositories.competitor_activity import CompetitorActivityRepository
from eop_api.repositories.visit import VisitRepository
from eop_api.schemas.competitor_activity import CompetitorActivityCreate, CompetitorActivityUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.services.visit_authorization import VisitAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class VisitNotFoundError(Exception):
    """Raised when the Visit referenced by a CompetitorActivity does not exist."""


class CompetitorActivityAuthorizationDeniedError(Exception):
    """Raised when the Visit Authorization Policy (Owner Only, evaluated
    against the CompetitorActivity's *parent Visit*) denies a
    create/get/update/delete call -- i.e. `AuthorizationDecision.allowed`
    is `False`.

    Thrown only by `CompetitorActivityService`, never by
    `VisitAuthorizationEvaluator` or `AuthorizationService` themselves.
    """


class CompetitorActivityService:
    """Business logic for `CompetitorActivity`. Owns the transaction
    boundary via a UoW.

    `CompetitorActivity` is a repeatable competitor observation attached to
    a `Visit` -- many rows may reference the same Visit (`docs/architecture/
    capabilities/competitor-activity/
    competitor-activity-iteration-1-scope-and-implementation-plan.md` §3),
    unlike `Survey`'s one-per-Visit shape. Only the existence of `visit_id`
    is validated here -- no duplicate-rejection check, since repeated
    observations for the same Visit are expected and permitted.

    Every `create`/`get`/`update`/`delete` call is gated by the Visit
    Authorization Policy (Owner Only), evaluated against the resolved
    *parent Visit* -- not a copy of `employee_id` on this entity itself,
    which does not exist (§6). This means authorization always reflects the
    Visit's current owner, even if `Visit.employee_id` is reassigned after
    this row is created. `VisitAuthorizationEvaluator` is reused completely
    unmodified via `_authorize`; this service never evaluates the policy
    itself. `list`/`list_paginated` are scoped to rows whose parent Visit
    belongs to the caller's own `employee_id`, mirroring `SurveyService`
    exactly.

    Returned entities are expunged from the unit-of-work's session before it
    closes: the UoW always rolls back (and thus expires all attributes) on
    exit, so callers holding on to the entity after this method returns would
    otherwise hit a `DetachedInstanceError` on first attribute access.

    `update` additionally refreshes the entity before expunging it, for the
    same server-side `onupdate` reason documented on `SurveyService.update`.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(
        self, data: CompetitorActivityCreate, request_context: RequestContext
    ) -> CompetitorActivity:
        async with self._uow_factory() as uow:
            visit = await VisitRepository(uow.session).get(data.visit_id)
            if visit is None:
                raise VisitNotFoundError(str(data.visit_id))

            await self._authorize(visit, request_context)

            repo = CompetitorActivityRepository(uow.session)
            activity = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(activity)
            return activity

    async def get(
        self, activity_id: uuid.UUID, request_context: RequestContext
    ) -> CompetitorActivity | None:
        async with self._uow_factory() as uow:
            activity = await CompetitorActivityRepository(uow.session).get(activity_id)
            if activity is None:
                return None

            visit = await VisitRepository(uow.session).get(activity.visit_id)
            assert visit is not None, "CompetitorActivity.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            uow.session.expunge(activity)
            return activity

    async def list_by_visit_id(
        self, visit_id: uuid.UUID, request_context: RequestContext
    ) -> Sequence[CompetitorActivity]:
        async with self._uow_factory() as uow:
            visit = await VisitRepository(uow.session).get(visit_id)
            if visit is None:
                raise VisitNotFoundError(str(visit_id))
            await self._authorize(visit, request_context)

            activities = await CompetitorActivityRepository(uow.session).list_by_visit_id(visit_id)
            uow.session.expunge_all()
            return activities

    async def list(self, request_context: RequestContext) -> Sequence[CompetitorActivity]:
        """CompetitorActivity rows whose parent Visit belongs to the
        caller's own `employee_id`.

        Loaded via `CompetitorActivityRepository.list()` plus a per-row
        parent-Visit lookup, mirroring `SurveyService.list` exactly --
        `CompetitorActivity` has no `employee_id` column to filter on
        directly.
        """
        async with self._uow_factory() as uow:
            activities = await CompetitorActivityRepository(uow.session).list()
            visit_repo = VisitRepository(uow.session)
            current_employee_id = request_context.employee_context.employee.id

            owned: list[CompetitorActivity] = []
            for activity in activities:
                visit = await visit_repo.get(activity.visit_id)
                if visit is not None and visit.employee_id == current_employee_id:
                    owned.append(activity)

            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self, request_context: RequestContext, pagination: PaginationParams
    ) -> Page[CompetitorActivity]:
        """CompetitorActivity rows whose parent Visit belongs to the
        caller's own `employee_id`, paginated at the SQL level via
        `CompetitorActivityRepository.paginate_by_employee_id` -- in-memory
        filtering after a DB-level `LIMIT` would return incorrect page
        slices, mirroring `SurveyService.list_paginated` exactly."""
        async with self._uow_factory() as uow:
            current_employee_id = request_context.employee_context.employee.id
            page = await CompetitorActivityRepository(uow.session).paginate_by_employee_id(
                current_employee_id, offset=pagination.offset, limit=pagination.limit
            )
            uow.session.expunge_all()
            return page

    async def update(
        self,
        activity_id: uuid.UUID,
        data: CompetitorActivityUpdate,
        request_context: RequestContext,
    ) -> CompetitorActivity | None:
        async with self._uow_factory() as uow:
            repo = CompetitorActivityRepository(uow.session)
            activity = await repo.get(activity_id)
            if activity is None:
                return None

            visit = await VisitRepository(uow.session).get(activity.visit_id)
            assert visit is not None, "CompetitorActivity.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            values = data.model_dump(exclude_unset=True)
            updated = await repo.update(activity_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, activity_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = CompetitorActivityRepository(uow.session)
            activity = await repo.get(activity_id)
            if activity is None:
                return False

            visit = await VisitRepository(uow.session).get(activity.visit_id)
            assert visit is not None, "CompetitorActivity.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            deleted = await repo.delete(activity_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Visit Authorization Policy (Owner Only) against
        `resource`, which is always the CompetitorActivity's parent `Visit`
        -- never the CompetitorActivity itself. `VisitAuthorizationEvaluator`
        is reused completely unmodified: it only ever inspects
        `resource.employee_id`, so passing the parent `Visit` is sufficient
        and requires no new evaluator class.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(VisitAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise CompetitorActivityAuthorizationDeniedError(
                decision.reason or "Competitor activity authorization denied"
            )
