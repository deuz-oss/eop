import uuid
from collections.abc import Callable, Sequence

from eop_api.models.shift import Shift
from eop_api.repositories.shift import ShiftRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.schemas.shift import ShiftCreate, ShiftUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateShiftCodeError(Exception):
    """Raised when a shift code is already in use."""


class InvalidShiftTimeError(Exception):
    """Raised when a shift's `start_time` and `end_time` are equal.

    Overnight shifts (`start_time > end_time`) are valid and intentionally
    not rejected here -- only an exactly equal pair is a business-rule
    violation, since it would describe a zero-length shift.
    """


class InvalidBreakDurationError(Exception):
    """Raised when a shift's `break_duration_minutes` is negative."""


class ShiftService:
    """Business logic for `Shift`. Owns the transaction boundary via a UoW.

    `Shift` is global master data -- it does not belong to an Organization,
    Department, Team, Position, or Location, and has no hierarchy.

    `start_time`/`end_time` and `break_duration_minutes` are validated
    against their *effective* values -- whichever values the shift will have
    once the request is applied, whether part of this request or already
    persisted -- mirroring `HrEmployeeService.update`'s effective-value
    pattern. This guarantees a partial `update()` can never leave a shift
    with an equal start/end pair or a negative break duration, even when the
    request only touches one of the related fields.

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

    async def create(self, data: ShiftCreate) -> Shift:
        async with self._uow_factory() as uow:
            repo = ShiftRepository(uow.session)

            if await repo.get_by_code(data.code):
                raise DuplicateShiftCodeError(data.code)

            if data.start_time == data.end_time:
                raise InvalidShiftTimeError(str(data.start_time))

            if data.break_duration_minutes < 0:
                raise InvalidBreakDurationError(str(data.break_duration_minutes))

            shift = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(shift)
            return shift

    async def get(self, shift_id: uuid.UUID) -> Shift | None:
        async with self._uow_factory() as uow:
            repo = ShiftRepository(uow.session)
            shift = await repo.get(shift_id)
            if shift is not None:
                uow.session.expunge(shift)
            return shift

    async def list(self) -> Sequence[Shift]:
        async with self._uow_factory() as uow:
            repo = ShiftRepository(uow.session)
            shifts = await repo.list()
            uow.session.expunge_all()
            return shifts

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Shift]:
        async with self._uow_factory() as uow:
            repo = ShiftRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, shift_id: uuid.UUID, data: ShiftUpdate) -> Shift | None:
        async with self._uow_factory() as uow:
            repo = ShiftRepository(uow.session)
            shift = await repo.get(shift_id)
            if shift is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != shift_id:
                    raise DuplicateShiftCodeError(values["code"])

            start_time = values.get("start_time", shift.start_time)
            end_time = values.get("end_time", shift.end_time)
            break_duration_minutes = values.get(
                "break_duration_minutes", shift.break_duration_minutes
            )

            if start_time == end_time:
                raise InvalidShiftTimeError(str(start_time))

            if break_duration_minutes < 0:
                raise InvalidBreakDurationError(str(break_duration_minutes))

            updated = await repo.update(shift_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, shift_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = ShiftRepository(uow.session)
            deleted = await repo.delete(shift_id)
            if deleted:
                await uow.commit()
            return deleted
