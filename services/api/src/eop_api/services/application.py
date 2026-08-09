import uuid
from collections.abc import Callable, Sequence

from eop_api.core.recruitment import VALID_APPLICATION_TRANSITIONS, ApplicationStatus
from eop_api.models.application import Application
from eop_api.repositories.application import ApplicationRepository
from eop_api.repositories.candidate import CandidateRepository
from eop_api.repositories.job_requisition import JobRequisitionRepository
from eop_api.schemas.application import ApplicationCreate, ApplicationUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class CandidateNotFoundError(Exception):
    """Raised when the candidate referenced by an Application does not exist."""


class JobRequisitionNotFoundError(Exception):
    """Raised when the job requisition referenced by an Application does not exist."""


class DuplicateApplicationError(Exception):
    """Raised when an Application already exists for the given candidate/job
    requisition pair."""


class InvalidApplicationTransitionError(Exception):
    """Raised when an `Application` lifecycle transition is attempted that is
    not present in `VALID_APPLICATION_TRANSITIONS` (`core/recruitment.py`).

    Per `docs/architecture/capabilities/recruitment/
    iteration-2-business-decision-package.md` (Approved, D1): forward-only,
    no backward transitions, no reopening a terminal state (`HIRED`/
    `REJECTED`/`WITHDRAWN` each map to an empty transition set). Mirrors
    `InvalidPayrollRunTransitionError`'s exact role for `PayrollRun`
    (`services/payroll_run.py`) -- there is no generic `status` setter.
    """


class ApplicationService:
    """Business logic for `Application`. Owns the transaction boundary via a UoW.

    Mirrors `AssignmentService`'s structure for CRUD (existence checks for
    both referenced aggregates, pair-uniqueness enforcement), and
    `PayrollRunService`'s structure for lifecycle (`transition`, a
    dedicated method validated against a fixed graph -- never a generic
    field update; `ApplicationUpdate` carries no `status` field at all).
    No organization-mismatch check is added, unlike `AssignmentService` --
    `Candidate` is not organization-scoped in this iteration
    (`iteration-1-scope-and-implementation-plan.md` §2).

    `transition` is a single, explicit, Recruitment-domain method backed by
    a fixed transition table -- not a generic workflow/state-machine
    abstraction (Rule 5 of the governing task: no speculative
    infrastructure). No cascading behavior exists between `JobRequisition`
    and `Application`: closing/deactivating a `JobRequisition` never
    mutates any `Application` (D2, Approved, Option A -- No Cascade).

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: ApplicationCreate) -> Application:
        async with self._uow_factory() as uow:
            if not await CandidateRepository(uow.session).exists(data.candidate_id):
                raise CandidateNotFoundError(str(data.candidate_id))

            if not await JobRequisitionRepository(uow.session).exists(data.job_requisition_id):
                raise JobRequisitionNotFoundError(str(data.job_requisition_id))

            repo = ApplicationRepository(uow.session)
            if await repo.get_by_candidate_and_requisition(
                data.candidate_id, data.job_requisition_id
            ):
                raise DuplicateApplicationError(f"{data.candidate_id}:{data.job_requisition_id}")

            application = await repo.create(**data.model_dump(), status=ApplicationStatus.APPLIED)
            await uow.commit()
            uow.session.expunge(application)
            return application

    async def get(self, application_id: uuid.UUID) -> Application | None:
        async with self._uow_factory() as uow:
            repo = ApplicationRepository(uow.session)
            application = await repo.get(application_id)
            if application is not None:
                uow.session.expunge(application)
            return application

    async def list(self) -> Sequence[Application]:
        async with self._uow_factory() as uow:
            repo = ApplicationRepository(uow.session)
            applications = await repo.list()
            uow.session.expunge_all()
            return applications

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Application]:
        async with self._uow_factory() as uow:
            repo = ApplicationRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, application_id: uuid.UUID, data: ApplicationUpdate
    ) -> Application | None:
        async with self._uow_factory() as uow:
            repo = ApplicationRepository(uow.session)
            application = await repo.get(application_id)
            if application is None:
                return None

            values = data.model_dump(exclude_unset=True)

            candidate_id = values.get("candidate_id", application.candidate_id)
            job_requisition_id = values.get("job_requisition_id", application.job_requisition_id)

            if "candidate_id" in values or "job_requisition_id" in values:
                if not await CandidateRepository(uow.session).exists(candidate_id):
                    raise CandidateNotFoundError(str(candidate_id))

                if not await JobRequisitionRepository(uow.session).exists(job_requisition_id):
                    raise JobRequisitionNotFoundError(str(job_requisition_id))

                existing = await repo.get_by_candidate_and_requisition(
                    candidate_id, job_requisition_id
                )
                if existing is not None and existing.id != application_id:
                    raise DuplicateApplicationError(f"{candidate_id}:{job_requisition_id}")

            updated = await repo.update(application_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def transition(
        self, application_id: uuid.UUID, target_status: ApplicationStatus
    ) -> Application | None:
        """Moves `application_id` to `target_status`, per
        `VALID_APPLICATION_TRANSITIONS` (`core/recruitment.py`).

        Returns `None` if `application_id` doesn't exist. Raises
        `InvalidApplicationTransitionError` if `target_status` is not a
        valid next state from the application's current `status` --
        including any attempt to leave a terminal state (`HIRED`/
        `REJECTED`/`WITHDRAWN`), which always fails since each maps to an
        empty transition set.
        """
        async with self._uow_factory() as uow:
            repo = ApplicationRepository(uow.session)
            application = await repo.get(application_id)
            if application is None:
                return None

            current_status = application.status
            if target_status not in VALID_APPLICATION_TRANSITIONS[current_status]:
                raise InvalidApplicationTransitionError(
                    f"Cannot move Application {application_id} from "
                    f"{current_status} to {target_status}"
                )

            updated = await repo.update(application_id, status=target_status)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, application_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = ApplicationRepository(uow.session)
            deleted = await repo.delete(application_id)
            if deleted:
                await uow.commit()
            return deleted
