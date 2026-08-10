import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.models.posm_audit import PosmAudit
from eop_api.repositories.posm_audit import PosmAuditRepository
from eop_api.repositories.visit import VisitRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.posm_audit import PosmAuditCreate, PosmAuditUpdate
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.services.visit_authorization import VisitAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class VisitNotFoundError(Exception):
    """Raised when the Visit referenced by a PosmAudit does not exist."""


class PosmAuditAuthorizationDeniedError(Exception):
    """Raised when the Visit Authorization Policy (Owner Only, evaluated
    against the PosmAudit's *parent Visit*) denies a create/get/update/
    delete call -- i.e. `AuthorizationDecision.allowed` is `False`.

    Thrown only by `PosmAuditService`, never by `VisitAuthorizationEvaluator`
    or `AuthorizationService` themselves.
    """


class PosmAuditService:
    """Business logic for `PosmAudit`. Owns the transaction boundary via a
    UoW.

    `PosmAudit` is a repeatable POSM (point-of-sale materials) observation
    attached to a `Visit` -- many rows may reference the same Visit
    (`docs/architecture/capabilities/posm-audit/
    posm-audit-iteration-1-scope-and-implementation-plan.md` §2/§3), the
    same cardinality as `CompetitorActivity`, unlike `Survey`'s one-per-Visit
    shape. Only the existence of `visit_id` is validated here -- no
    duplicate-rejection check, since repeated observations for the same
    Visit are expected and permitted.

    Every `create`/`get`/`update`/`delete` call is gated by the Visit
    Authorization Policy (Owner Only), evaluated against the resolved
    *parent Visit* -- not a copy of `employee_id` on this entity itself,
    which does not exist (§4). This means authorization always reflects the
    Visit's current owner, even if `Visit.employee_id` is reassigned after
    this row is created. `VisitAuthorizationEvaluator` is reused completely
    unmodified via `_authorize`; this service never evaluates the policy
    itself. `list`/`list_paginated` are scoped to rows whose parent Visit
    belongs to the caller's own `employee_id`, mirroring
    `CompetitorActivityService` exactly.

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

    async def create(self, data: PosmAuditCreate, request_context: RequestContext) -> PosmAudit:
        async with self._uow_factory() as uow:
            visit = await VisitRepository(uow.session).get(data.visit_id)
            if visit is None:
                raise VisitNotFoundError(str(data.visit_id))

            await self._authorize(visit, request_context)

            repo = PosmAuditRepository(uow.session)
            audit = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(audit)
            return audit

    async def get(self, audit_id: uuid.UUID, request_context: RequestContext) -> PosmAudit | None:
        async with self._uow_factory() as uow:
            audit = await PosmAuditRepository(uow.session).get(audit_id)
            if audit is None:
                return None

            visit = await VisitRepository(uow.session).get(audit.visit_id)
            assert visit is not None, "PosmAudit.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            uow.session.expunge(audit)
            return audit

    async def list(self, request_context: RequestContext) -> Sequence[PosmAudit]:
        """PosmAudit rows whose parent Visit belongs to the caller's own
        `employee_id`.

        Loaded via `PosmAuditRepository.list()` plus a per-row parent-Visit
        lookup, mirroring `CompetitorActivityService.list` exactly --
        `PosmAudit` has no `employee_id` column to filter on directly.
        """
        async with self._uow_factory() as uow:
            audits = await PosmAuditRepository(uow.session).list()
            visit_repo = VisitRepository(uow.session)
            current_employee_id = request_context.employee_context.employee.id

            owned: list[PosmAudit] = []
            for audit in audits:
                visit = await visit_repo.get(audit.visit_id)
                if visit is not None and visit.employee_id == current_employee_id:
                    owned.append(audit)

            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self,
        request_context: RequestContext,
        pagination: PaginationParams,
        *,
        visit_id: uuid.UUID | None = None,
    ) -> Page[PosmAudit]:
        """PosmAudit rows whose parent Visit belongs to the caller's own
        `employee_id`, paginated at the SQL level via
        `PosmAuditRepository.paginate_by_employee_id` -- in-memory filtering
        after a DB-level `LIMIT` would return incorrect page slices,
        mirroring `CompetitorActivityService.list_paginated`. `visit_id` is
        an optional further filter, layered onto the same Owner Only-scoped
        query."""
        async with self._uow_factory() as uow:
            current_employee_id = request_context.employee_context.employee.id
            page = await PosmAuditRepository(uow.session).paginate_by_employee_id(
                current_employee_id,
                offset=pagination.offset,
                limit=pagination.limit,
                visit_id=visit_id,
            )
            uow.session.expunge_all()
            return page

    async def update(
        self,
        audit_id: uuid.UUID,
        data: PosmAuditUpdate,
        request_context: RequestContext,
    ) -> PosmAudit | None:
        async with self._uow_factory() as uow:
            repo = PosmAuditRepository(uow.session)
            audit = await repo.get(audit_id)
            if audit is None:
                return None

            visit = await VisitRepository(uow.session).get(audit.visit_id)
            assert visit is not None, "PosmAudit.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            values = data.model_dump(exclude_unset=True)
            updated = await repo.update(audit_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, audit_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = PosmAuditRepository(uow.session)
            audit = await repo.get(audit_id)
            if audit is None:
                return False

            visit = await VisitRepository(uow.session).get(audit.visit_id)
            assert visit is not None, "PosmAudit.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            deleted = await repo.delete(audit_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Visit Authorization Policy (Owner Only) against
        `resource`, which is always the PosmAudit's parent `Visit` -- never
        the PosmAudit itself. `VisitAuthorizationEvaluator` is reused
        completely unmodified: it only ever inspects `resource.employee_id`,
        so passing the parent `Visit` is sufficient and requires no new
        evaluator class.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(VisitAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise PosmAuditAuthorizationDeniedError(
                decision.reason or "POSM audit authorization denied"
            )
