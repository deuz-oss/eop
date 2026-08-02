import uuid
from collections.abc import Callable, Sequence

from eop_api.models.job_grade import JobGrade
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.schemas.job_grade import JobGradeCreate, JobGradeUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateJobGradeCodeError(Exception):
    """Raised when a job grade code is already in use."""


class DuplicateJobGradeLevelError(Exception):
    """Raised when a job grade level is already in use."""


class JobGradeService:
    """Business logic for `JobGrade`. Owns the transaction boundary via a UoW.

    `JobGrade` is global master data -- it does not belong to an
    Organization, Department, Team, or Position, and has no hierarchy.

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

    async def create(self, data: JobGradeCreate) -> JobGrade:
        async with self._uow_factory() as uow:
            repo = JobGradeRepository(uow.session)

            if await repo.get_by_code(data.code):
                raise DuplicateJobGradeCodeError(data.code)
            if await repo.get_by_level(data.level):
                raise DuplicateJobGradeLevelError(str(data.level))

            job_grade = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(job_grade)
            return job_grade

    async def get(self, job_grade_id: uuid.UUID) -> JobGrade | None:
        async with self._uow_factory() as uow:
            repo = JobGradeRepository(uow.session)
            job_grade = await repo.get(job_grade_id)
            if job_grade is not None:
                uow.session.expunge(job_grade)
            return job_grade

    async def list(self) -> Sequence[JobGrade]:
        async with self._uow_factory() as uow:
            repo = JobGradeRepository(uow.session)
            job_grades = await repo.list()
            uow.session.expunge_all()
            return job_grades

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[JobGrade]:
        async with self._uow_factory() as uow:
            repo = JobGradeRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, job_grade_id: uuid.UUID, data: JobGradeUpdate) -> JobGrade | None:
        async with self._uow_factory() as uow:
            repo = JobGradeRepository(uow.session)
            job_grade = await repo.get(job_grade_id)
            if job_grade is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != job_grade_id:
                    raise DuplicateJobGradeCodeError(values["code"])

            if "level" in values:
                existing = await repo.get_by_level(values["level"])
                if existing is not None and existing.id != job_grade_id:
                    raise DuplicateJobGradeLevelError(str(values["level"]))

            updated = await repo.update(job_grade_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, job_grade_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = JobGradeRepository(uow.session)
            deleted = await repo.delete(job_grade_id)
            if deleted:
                await uow.commit()
            return deleted
