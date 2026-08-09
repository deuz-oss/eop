import uuid
from collections.abc import Callable, Sequence

from eop_api.models.candidate import Candidate
from eop_api.repositories.candidate import CandidateRepository
from eop_api.schemas.candidate import CandidateCreate, CandidateUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateCandidateEmailError(Exception):
    """Raised when a candidate email is already in use."""


class CandidateService:
    """Business logic for `Candidate`. Owns the transaction boundary via a UoW.

    Mirrors `ShiftService`'s structure -- master-data-shaped CRUD, no
    dedicated authorization evaluator (`CurrentUser`-only at the API layer).
    Candidates are not `HrEmployee`s (`iteration-1-scope-and-
    implementation-plan.md` §1); no relationship to HR/employee data exists
    or is added here.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: CandidateCreate) -> Candidate:
        async with self._uow_factory() as uow:
            repo = CandidateRepository(uow.session)

            if await repo.get_by_email(data.email):
                raise DuplicateCandidateEmailError(data.email)

            candidate = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(candidate)
            return candidate

    async def get(self, candidate_id: uuid.UUID) -> Candidate | None:
        async with self._uow_factory() as uow:
            repo = CandidateRepository(uow.session)
            candidate = await repo.get(candidate_id)
            if candidate is not None:
                uow.session.expunge(candidate)
            return candidate

    async def list(self) -> Sequence[Candidate]:
        async with self._uow_factory() as uow:
            repo = CandidateRepository(uow.session)
            candidates = await repo.list()
            uow.session.expunge_all()
            return candidates

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Candidate]:
        async with self._uow_factory() as uow:
            repo = CandidateRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, candidate_id: uuid.UUID, data: CandidateUpdate) -> Candidate | None:
        async with self._uow_factory() as uow:
            repo = CandidateRepository(uow.session)
            candidate = await repo.get(candidate_id)
            if candidate is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "email" in values:
                existing = await repo.get_by_email(values["email"])
                if existing is not None and existing.id != candidate_id:
                    raise DuplicateCandidateEmailError(values["email"])

            updated = await repo.update(candidate_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, candidate_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = CandidateRepository(uow.session)
            deleted = await repo.delete(candidate_id)
            if deleted:
                await uow.commit()
            return deleted
