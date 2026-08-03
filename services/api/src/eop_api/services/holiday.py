import uuid
from collections.abc import Callable, Sequence

from eop_api.models.holiday import Holiday
from eop_api.repositories.holiday import HolidayRepository
from eop_api.schemas.holiday import HolidayCreate, HolidayUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateHolidayCodeError(Exception):
    """Raised when a holiday code is already in use."""


class DuplicateHolidayDateError(Exception):
    """Raised when a holiday date is already in use."""


class HolidayService:
    """Business logic for `Holiday`. Owns the transaction boundary via a UoW.

    `Holiday` is global master data -- it does not belong to an Organization,
    Department, Team, Position, or Location, and has no hierarchy.

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

    async def create(self, data: HolidayCreate) -> Holiday:
        async with self._uow_factory() as uow:
            repo = HolidayRepository(uow.session)

            if await repo.get_by_code(data.code):
                raise DuplicateHolidayCodeError(data.code)

            if await repo.get_by_holiday_date(data.holiday_date):
                raise DuplicateHolidayDateError(str(data.holiday_date))

            holiday = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(holiday)
            return holiday

    async def get(self, holiday_id: uuid.UUID) -> Holiday | None:
        async with self._uow_factory() as uow:
            repo = HolidayRepository(uow.session)
            holiday = await repo.get(holiday_id)
            if holiday is not None:
                uow.session.expunge(holiday)
            return holiday

    async def list(self) -> Sequence[Holiday]:
        async with self._uow_factory() as uow:
            repo = HolidayRepository(uow.session)
            holidays = await repo.list()
            uow.session.expunge_all()
            return holidays

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Holiday]:
        async with self._uow_factory() as uow:
            repo = HolidayRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, holiday_id: uuid.UUID, data: HolidayUpdate) -> Holiday | None:
        async with self._uow_factory() as uow:
            repo = HolidayRepository(uow.session)
            holiday = await repo.get(holiday_id)
            if holiday is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != holiday_id:
                    raise DuplicateHolidayCodeError(values["code"])

            if "holiday_date" in values:
                existing = await repo.get_by_holiday_date(values["holiday_date"])
                if existing is not None and existing.id != holiday_id:
                    raise DuplicateHolidayDateError(str(values["holiday_date"]))

            updated = await repo.update(holiday_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, holiday_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = HolidayRepository(uow.session)
            deleted = await repo.delete(holiday_id)
            if deleted:
                await uow.commit()
            return deleted
