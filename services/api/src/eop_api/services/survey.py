import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.models.survey import Survey
from eop_api.repositories.survey import SurveyRepository
from eop_api.repositories.visit import VisitRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.survey import SurveyCreate, SurveyUpdate
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.services.visit_authorization import VisitAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class VisitNotFoundError(Exception):
    """Raised when the Visit referenced by a Survey does not exist."""


class DuplicateSurveyError(Exception):
    """Raised when the referenced Visit already has a Survey.

    One Survey per Visit (`docs/architecture/capabilities/survey/
    iteration-1-scope-and-implementation-plan.md` §2/§4), enforced at the
    database level via `Survey.visit_id`'s `UniqueConstraint` -- this
    exception surfaces the same refusal as an explicit application error
    instead of an unhandled `IntegrityError`.
    """


class SurveyAuthorizationDeniedError(Exception):
    """Raised when the Visit Authorization Policy (Owner Only, evaluated
    against the Survey's *parent Visit*) denies a create/get/update/delete
    call -- i.e. `AuthorizationDecision.allowed` is `False`.

    Thrown only by `SurveyService`, never by `VisitAuthorizationEvaluator`
    or `AuthorizationService` themselves.
    """


class SurveyService:
    """Business logic for `Survey`. Owns the transaction boundary via a UoW.

    `Survey` is a fixed, three-question record attached to one `Visit` --
    not a configurable questionnaire, not a status/workflow entity. Only
    the existence of `visit_id` and the one-per-visit constraint are
    validated here.

    Every `create`/`get`/`update`/`delete` call is gated by the Visit
    Authorization Policy (Owner Only), evaluated against the Survey's
    resolved *parent Visit* -- not a copy of `employee_id` on `Survey`
    itself, which does not exist (`iteration-1-scope-and-implementation-
    plan.md` §5). This means authorization always reflects the Visit's
    current owner, even if `Visit.employee_id` is reassigned after the
    Survey is created. `VisitAuthorizationEvaluator` is reused completely
    unmodified via `_authorize`; this service never evaluates the policy
    itself. `list`/`list_paginated` are scoped to Surveys whose parent
    Visit belongs to the caller's own `employee_id`, mirroring
    `VisitService`'s own scoping posture.

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

    async def create(self, data: SurveyCreate, request_context: RequestContext) -> Survey:
        async with self._uow_factory() as uow:
            visit = await VisitRepository(uow.session).get(data.visit_id)
            if visit is None:
                raise VisitNotFoundError(str(data.visit_id))

            await self._authorize(visit, request_context)

            repo = SurveyRepository(uow.session)
            if await repo.get_by_visit_id(data.visit_id) is not None:
                raise DuplicateSurveyError(str(data.visit_id))

            survey = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(survey)
            return survey

    async def get(self, survey_id: uuid.UUID, request_context: RequestContext) -> Survey | None:
        async with self._uow_factory() as uow:
            survey = await SurveyRepository(uow.session).get(survey_id)
            if survey is None:
                return None

            visit = await VisitRepository(uow.session).get(survey.visit_id)
            assert visit is not None, "Survey.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            uow.session.expunge(survey)
            return survey

    async def get_by_visit_id(
        self, visit_id: uuid.UUID, request_context: RequestContext
    ) -> Survey | None:
        async with self._uow_factory() as uow:
            visit = await VisitRepository(uow.session).get(visit_id)
            if visit is None:
                return None
            await self._authorize(visit, request_context)

            survey = await SurveyRepository(uow.session).get_by_visit_id(visit_id)
            if survey is not None:
                uow.session.expunge(survey)
            return survey

    async def list(self, request_context: RequestContext) -> Sequence[Survey]:
        """Surveys whose parent Visit belongs to the caller's own `employee_id`.

        Loaded via `SurveyRepository.list()` plus a per-row parent-Visit
        lookup, mirroring `AttendanceEventService.list`'s own in-memory
        filtering shape -- `Survey` has no `employee_id` column to filter
        on directly (§5).
        """
        async with self._uow_factory() as uow:
            surveys = await SurveyRepository(uow.session).list()
            visit_repo = VisitRepository(uow.session)
            current_employee_id = request_context.employee_context.employee.id

            owned: list[Survey] = []
            for survey in surveys:
                visit = await visit_repo.get(survey.visit_id)
                if visit is not None and visit.employee_id == current_employee_id:
                    owned.append(survey)

            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self, request_context: RequestContext, pagination: PaginationParams
    ) -> Page[Survey]:
        """Surveys whose parent Visit belongs to the caller's own
        `employee_id`, paginated at the SQL level via
        `SurveyRepository.paginate_by_employee_id` (§5 -- in-memory
        filtering after a DB-level `LIMIT` would return incorrect page
        slices)."""
        async with self._uow_factory() as uow:
            current_employee_id = request_context.employee_context.employee.id
            page = await SurveyRepository(uow.session).paginate_by_employee_id(
                current_employee_id, offset=pagination.offset, limit=pagination.limit
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, survey_id: uuid.UUID, data: SurveyUpdate, request_context: RequestContext
    ) -> Survey | None:
        async with self._uow_factory() as uow:
            repo = SurveyRepository(uow.session)
            survey = await repo.get(survey_id)
            if survey is None:
                return None

            visit = await VisitRepository(uow.session).get(survey.visit_id)
            assert visit is not None, "Survey.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            values = data.model_dump(exclude_unset=True)
            updated = await repo.update(survey_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, survey_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = SurveyRepository(uow.session)
            survey = await repo.get(survey_id)
            if survey is None:
                return False

            visit = await VisitRepository(uow.session).get(survey.visit_id)
            assert visit is not None, "Survey.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            deleted = await repo.delete(survey_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Visit Authorization Policy (Owner Only) against
        `resource`, which is always the Survey's parent `Visit` -- never
        the Survey itself. `VisitAuthorizationEvaluator` is reused
        completely unmodified: it only ever inspects `resource.employee_id`,
        so passing the parent `Visit` is sufficient and requires no new
        evaluator class.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(VisitAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise SurveyAuthorizationDeniedError(decision.reason or "Survey authorization denied")
