import uuid
from collections.abc import Callable, Sequence

from eop_api.models.attendance_event import AttendanceEvent
from eop_api.repositories.attendance_event import AttendanceEventRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.schemas.attendance_event import AttendanceEventCreate, AttendanceEventUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by an AttendanceEvent does not exist."""


class ShiftNotFoundError(Exception):
    """Raised when the shift referenced by an AttendanceEvent does not exist."""


class AttendanceEventService:
    """Business logic for `AttendanceEvent`. Owns the transaction boundary via a UoW.

    `AttendanceEvent` is a single clock transaction (clock-in/out, break-in/out)
    -- not an employee-day summary, timesheet, or payroll record. Only the
    existence of `employee_id` and `shift_id` is validated here. Sequencing
    (e.g. rejecting a clock-out before a clock-in), duplicate-event detection,
    and shift-matching are explicitly out of scope for this module and belong
    to future business-workflow PRs.

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

    async def create(self, data: AttendanceEventCreate) -> AttendanceEvent:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if not await ShiftRepository(uow.session).exists(data.shift_id):
                raise ShiftNotFoundError(str(data.shift_id))

            event = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(event)
            return event

    async def get(self, event_id: uuid.UUID) -> AttendanceEvent | None:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is not None:
                uow.session.expunge(event)
            return event

    async def list(self) -> Sequence[AttendanceEvent]:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            events = await repo.list()
            uow.session.expunge_all()
            return events

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[AttendanceEvent]:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, event_id: uuid.UUID, data: AttendanceEventUpdate
    ) -> AttendanceEvent | None:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            event = await repo.get(event_id)
            if event is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            if "shift_id" in values:
                if not await ShiftRepository(uow.session).exists(values["shift_id"]):
                    raise ShiftNotFoundError(str(values["shift_id"]))

            updated = await repo.update(event_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, event_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = AttendanceEventRepository(uow.session)
            deleted = await repo.delete(event_id)
            if deleted:
                await uow.commit()
            return deleted
