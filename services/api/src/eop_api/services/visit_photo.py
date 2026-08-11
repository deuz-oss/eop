import uuid
from collections.abc import Callable, Sequence
from typing import Any

from eop_api.models.visit_photo import VisitPhoto
from eop_api.repositories.file import FileRepository
from eop_api.repositories.visit import VisitRepository
from eop_api.repositories.visit_photo import VisitPhotoRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.visit_photo import VisitPhotoCreate, VisitPhotoUpdate
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.employee_context import RequestContext
from eop_api.services.visit_authorization import VisitAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class VisitNotFoundError(Exception):
    """Raised when the Visit referenced by a VisitPhoto does not exist."""


class FileObjectNotFoundError(Exception):
    """Raised when the FileObject referenced by `file_object_id` does not exist."""


class VisitPhotoAuthorizationDeniedError(Exception):
    """Raised when the Visit Authorization Policy (Owner Only, evaluated
    against the VisitPhoto's *parent Visit*) denies a create/get/update/
    delete call -- i.e. `AuthorizationDecision.allowed` is `False`.

    Thrown only by `VisitPhotoService`, never by `VisitAuthorizationEvaluator`
    or `AuthorizationService` themselves.
    """


class VisitPhotoService:
    """Business logic for `VisitPhoto`. Owns the transaction boundary via
    a UoW.

    `VisitPhoto` is a repeatable photo attachment to a `Visit` -- many rows
    may reference the same Visit (`docs/architecture/capabilities/
    photo-evidence/photo-evidence-iteration-1-scope-and-implementation-
    plan.md` §2/§3), the same cardinality as `CompetitorActivity`/
    `PosmAudit`, unlike `Survey`'s one-per-Visit shape. Only the existence
    of `visit_id` and `file_object_id` is validated here -- no
    duplicate-rejection check, since multiple photos per Visit are expected
    and permitted.

    Every `create`/`get`/`update`/`delete` call is gated by the Visit
    Authorization Policy (Owner Only), evaluated against the resolved
    *parent Visit* -- not a copy of `employee_id` on this entity itself,
    which does not exist (§4). This means authorization always reflects the
    Visit's current owner, even if `Visit.employee_id` is reassigned after
    this row is created. `VisitAuthorizationEvaluator` is reused completely
    unmodified via `_authorize`; this service never evaluates the policy
    itself. `list`/`list_paginated` are scoped to rows whose parent Visit
    belongs to the caller's own `employee_id`, mirroring
    `PosmAuditService` exactly.

    Returned entities are expunged from the unit-of-work's session before it
    closes: the UoW always rolls back (and thus expires all attributes) on
    exit, so callers holding on to the entity after this method returns would
    otherwise hit a `DetachedInstanceError` on first attribute access.

    `update` additionally refreshes the entity before expunging it, for the
    same server-side `onupdate` reason documented on `PosmAuditService.
    update`.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: VisitPhotoCreate, request_context: RequestContext) -> VisitPhoto:
        async with self._uow_factory() as uow:
            visit = await VisitRepository(uow.session).get(data.visit_id)
            if visit is None:
                raise VisitNotFoundError(str(data.visit_id))

            if not await FileRepository(uow.session).exists(data.file_object_id):
                raise FileObjectNotFoundError(str(data.file_object_id))

            await self._authorize(visit, request_context)

            repo = VisitPhotoRepository(uow.session)
            photo = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(photo)
            return photo

    async def get(self, photo_id: uuid.UUID, request_context: RequestContext) -> VisitPhoto | None:
        async with self._uow_factory() as uow:
            photo = await VisitPhotoRepository(uow.session).get(photo_id)
            if photo is None:
                return None

            visit = await VisitRepository(uow.session).get(photo.visit_id)
            assert visit is not None, "VisitPhoto.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            uow.session.expunge(photo)
            return photo

    async def list(self, request_context: RequestContext) -> Sequence[VisitPhoto]:
        """VisitPhoto rows whose parent Visit belongs to the caller's own
        `employee_id`.

        Loaded via `VisitPhotoRepository.list()` plus a per-row parent-Visit
        lookup, mirroring `PosmAuditService.list` exactly -- `VisitPhoto`
        has no `employee_id` column to filter on directly.
        """
        async with self._uow_factory() as uow:
            photos = await VisitPhotoRepository(uow.session).list()
            visit_repo = VisitRepository(uow.session)
            current_employee_id = request_context.employee_context.employee.id

            owned: list[VisitPhoto] = []
            for photo in photos:
                visit = await visit_repo.get(photo.visit_id)
                if visit is not None and visit.employee_id == current_employee_id:
                    owned.append(photo)

            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self,
        request_context: RequestContext,
        pagination: PaginationParams,
        *,
        visit_id: uuid.UUID | None = None,
    ) -> Page[VisitPhoto]:
        """VisitPhoto rows whose parent Visit belongs to the caller's own
        `employee_id`, paginated at the SQL level via
        `VisitPhotoRepository.paginate_by_employee_id` -- in-memory
        filtering after a DB-level `LIMIT` would return incorrect page
        slices, mirroring `PosmAuditService.list_paginated` exactly.
        `visit_id` is an optional further filter, layered onto the same
        Owner Only-scoped query."""
        async with self._uow_factory() as uow:
            current_employee_id = request_context.employee_context.employee.id
            page = await VisitPhotoRepository(uow.session).paginate_by_employee_id(
                current_employee_id,
                offset=pagination.offset,
                limit=pagination.limit,
                visit_id=visit_id,
            )
            uow.session.expunge_all()
            return page

    async def update(
        self,
        photo_id: uuid.UUID,
        data: VisitPhotoUpdate,
        request_context: RequestContext,
    ) -> VisitPhoto | None:
        async with self._uow_factory() as uow:
            repo = VisitPhotoRepository(uow.session)
            photo = await repo.get(photo_id)
            if photo is None:
                return None

            visit = await VisitRepository(uow.session).get(photo.visit_id)
            assert visit is not None, "VisitPhoto.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            values = data.model_dump(exclude_unset=True)

            if "file_object_id" in values:
                if not await FileRepository(uow.session).exists(values["file_object_id"]):
                    raise FileObjectNotFoundError(str(values["file_object_id"]))

            updated = await repo.update(photo_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, photo_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = VisitPhotoRepository(uow.session)
            photo = await repo.get(photo_id)
            if photo is None:
                return False

            visit = await VisitRepository(uow.session).get(photo.visit_id)
            assert visit is not None, "VisitPhoto.visit_id is ON DELETE RESTRICT"
            await self._authorize(visit, request_context)

            deleted = await repo.delete(photo_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Visit Authorization Policy (Owner Only) against
        `resource`, which is always the VisitPhoto's parent `Visit` -- never
        the VisitPhoto itself. `VisitAuthorizationEvaluator` is reused
        completely unmodified: it only ever inspects `resource.employee_id`,
        so passing the parent `Visit` is sufficient and requires no new
        evaluator class.
        """
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(VisitAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise VisitPhotoAuthorizationDeniedError(
                decision.reason or "Visit photo authorization denied"
            )
