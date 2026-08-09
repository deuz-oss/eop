import uuid
from collections.abc import Callable, Sequence

from eop_api.models.interview import Interview
from eop_api.repositories.application import ApplicationRepository
from eop_api.repositories.interview import InterviewRepository
from eop_api.schemas.interview import InterviewCreate, InterviewUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class ApplicationNotFoundError(Exception):
    """Raised when the application referenced by an Interview does not exist."""


class InterviewService:
    """Business logic for `Interview`. Owns the transaction boundary via a UoW.

    Deliberately minimal: a single existence check on `application_id`, no
    uniqueness constraint (multiple interviews per `Application` are
    permitted), no lifecycle/status of its own -- `Application` owns the
    recruitment lifecycle (Iteration 2). No coupling to
    `ApplicationService.transition` exists here.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: InterviewCreate) -> Interview:
        async with self._uow_factory() as uow:
            if not await ApplicationRepository(uow.session).exists(data.application_id):
                raise ApplicationNotFoundError(str(data.application_id))

            interview = await InterviewRepository(uow.session).create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(interview)
            return interview

    async def get(self, interview_id: uuid.UUID) -> Interview | None:
        async with self._uow_factory() as uow:
            interview = await InterviewRepository(uow.session).get(interview_id)
            if interview is not None:
                uow.session.expunge(interview)
            return interview

    async def list(self) -> Sequence[Interview]:
        async with self._uow_factory() as uow:
            interviews = await InterviewRepository(uow.session).list()
            uow.session.expunge_all()
            return interviews

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Interview]:
        async with self._uow_factory() as uow:
            page = await InterviewRepository(uow.session).paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, interview_id: uuid.UUID, data: InterviewUpdate) -> Interview | None:
        async with self._uow_factory() as uow:
            repo = InterviewRepository(uow.session)
            interview = await repo.get(interview_id)
            if interview is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "application_id" in values and not await ApplicationRepository(uow.session).exists(
                values["application_id"]
            ):
                raise ApplicationNotFoundError(str(values["application_id"]))

            updated = await repo.update(interview_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, interview_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = InterviewRepository(uow.session)
            deleted = await repo.delete(interview_id)
            if deleted:
                await uow.commit()
            return deleted
