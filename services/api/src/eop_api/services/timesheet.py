import uuid
from collections.abc import Callable, Sequence

from eop_api.models.timesheet import Timesheet
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.timesheet import TimesheetRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.schemas.timesheet import TimesheetCreate, TimesheetUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Timesheet does not exist."""


class InvalidTimesheetDateRangeError(Exception):
    """Raised when a Timesheet's `end_date` is earlier than its `start_date`."""


class TimesheetService:
    """Business logic for `Timesheet`. Owns the transaction boundary via a UoW.

    `Timesheet` is a single employee's submission for a dated span -- not a
    calculation or reconciliation record. Only the existence of `employee_id`
    and `start_date <= end_date` are validated on `create`/`update`. `status`,
    `approved_by`, `approved_at`, and `rejection_reason` are storage-only
    columns here -- no transition validation, authorization, audit logging,
    or event/notification dispatch is performed by this service. Which
    component orchestrates an approval decision is an intentionally
    unresolved architectural question (per
    `docs/architecture/APPROVAL_WORKFLOW_DESIGN.md` §10) and is deferred to a
    future PR, not decided here. Attendance/overtime/leave/holiday
    reconciliation, computed hour totals, overlap detection, duplicate
    detection, and payroll integration remain out of scope per
    `docs/architecture/TIMESHEET_DESIGN.md`.

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

    async def create(self, data: TimesheetCreate) -> Timesheet:
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if data.end_date < data.start_date:
                raise InvalidTimesheetDateRangeError(
                    f"end_date {data.end_date} is before start_date {data.start_date}"
                )

            timesheet = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(timesheet)
            return timesheet

    async def get(self, timesheet_id: uuid.UUID) -> Timesheet | None:
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)
            timesheet = await repo.get(timesheet_id)
            if timesheet is not None:
                uow.session.expunge(timesheet)
            return timesheet

    async def list(self) -> Sequence[Timesheet]:
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)
            timesheets = await repo.list()
            uow.session.expunge_all()
            return timesheets

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Timesheet]:
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, timesheet_id: uuid.UUID, data: TimesheetUpdate) -> Timesheet | None:
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)
            timesheet = await repo.get(timesheet_id)
            if timesheet is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            start_date = values.get("start_date", timesheet.start_date)
            end_date = values.get("end_date", timesheet.end_date)

            if end_date < start_date:
                raise InvalidTimesheetDateRangeError(
                    f"end_date {end_date} is before start_date {start_date}"
                )

            updated = await repo.update(timesheet_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, timesheet_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)
            deleted = await repo.delete(timesheet_id)
            if deleted:
                await uow.commit()
            return deleted
