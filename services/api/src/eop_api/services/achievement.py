import uuid
from collections.abc import Callable, Sequence

from eop_api.models.achievement import Achievement
from eop_api.repositories.achievement import AchievementRepository
from eop_api.repositories.target import TargetRepository
from eop_api.schemas.achievement import AchievementCreate, AchievementUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class TargetNotFoundError(Exception):
    """Raised when the Target referenced by an Achievement does not exist."""


class DuplicateAchievementError(Exception):
    """Raised when an Achievement already exists for the same target_id.

    Enforced at the database level via `Achievement`'s `UniqueConstraint`
    (`uq_achievements_target_id`) -- this exception surfaces the same
    refusal as an explicit application error instead of an unhandled
    `IntegrityError`, mirroring `DuplicateTargetError`/`DuplicateSurveyError`'s
    check-then-insert shape.
    """


class AchievementService:
    """Business logic for `Achievement`. Owns the transaction boundary via a UoW.

    `Achievement` is a manually entered actual value against exactly one
    `Target` (`docs/architecture/capabilities/performance/
    achievement-iteration-1-scope-and-implementation-plan.md`). `create()`
    validates that `target_id` references an existing row and that no
    Achievement already exists for it.

    Authorization is Role Based (`RequireRole("admin")`, enforced entirely
    at the API layer via `RequireAchievementAdmin`) -- no Owner Only
    evaluator exists for `Achievement`, mirroring `TargetService` exactly:
    this service performs no authorization check of its own.

    `update()` only ever changes `actual_value` -- `AchievementUpdate`
    carries no other field, so `target_id` can never be modified through
    this method.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository. `update`
    additionally refreshes the entity before expunging it, for the same
    `updated_at` server-side `onupdate` reason documented on
    `TargetService.update`/`SurveyService.update`.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: AchievementCreate) -> Achievement:
        async with self._uow_factory() as uow:
            if not await TargetRepository(uow.session).exists(data.target_id):
                raise TargetNotFoundError(str(data.target_id))

            repo = AchievementRepository(uow.session)
            existing = await repo.get_by_target_id(data.target_id)
            if existing is not None:
                raise DuplicateAchievementError(str(data.target_id))

            achievement = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(achievement)
            return achievement

    async def get(self, achievement_id: uuid.UUID) -> Achievement | None:
        async with self._uow_factory() as uow:
            repo = AchievementRepository(uow.session)
            achievement = await repo.get(achievement_id)
            if achievement is not None:
                uow.session.expunge(achievement)
            return achievement

    async def list(self) -> Sequence[Achievement]:
        async with self._uow_factory() as uow:
            repo = AchievementRepository(uow.session)
            achievements = await repo.list()
            uow.session.expunge_all()
            return achievements

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Achievement]:
        async with self._uow_factory() as uow:
            repo = AchievementRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, achievement_id: uuid.UUID, data: AchievementUpdate
    ) -> Achievement | None:
        async with self._uow_factory() as uow:
            repo = AchievementRepository(uow.session)
            achievement = await repo.get(achievement_id)
            if achievement is None:
                return None

            values = data.model_dump(exclude_unset=True)

            updated = await repo.update(achievement_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, achievement_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = AchievementRepository(uow.session)
            deleted = await repo.delete(achievement_id)
            if deleted:
                await uow.commit()
            return deleted
