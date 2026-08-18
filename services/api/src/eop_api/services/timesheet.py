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


class InvalidTimesheetStateError(Exception):
    """Raised when `update` is attempted on a `Timesheet` whose persisted
    status isn't `pending` (no exceptions per field -- a client cannot use a
    generic field update, including `status`, to reach `approved` outside
    `ApprovalService`). Mirrors `ApprovalService.InvalidApprovalStateError`'s
    precedent for the same class of workflow-state invariant.
    """


class TimesheetService:
    """Business logic for `Timesheet`. Owns the transaction boundary via a UoW.

    `Timesheet` is a single employee's submission for a dated span -- not a
    calculation or reconciliation record. `ApprovalService`
    (`services/approval.py`) owns approve/reject orchestration -- the
    `pending -> approved`/`pending -> rejected` transitions and their
    authorization -- and is the only path to those transitions.
    `TimesheetService` owns `Timesheet` CRUD and the `pending`-only mutation
    rule enforced here: `create` needs only `employee_id` existence and
    `start_date <= end_date`, and always forces the new row's `status` to
    `pending` regardless of any client-supplied value; `update` additionally
    requires the persisted entity's `status` to be `pending` (no field is
    exempt -- including `status` itself, which closes the generic-update
    path as a way to reach `approved` outside `ApprovalService`). No audit
    logging or event/notification dispatch is performed by this service.
    Attendance/overtime/leave/holiday reconciliation, computed hour totals,
    overlap detection, duplicate detection, and payroll integration remain
    out of scope per `docs/architecture/TIMESHEET_DESIGN.md`.

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

            timesheet = await repo.create(**data.model_dump(), status="pending")
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

            if timesheet.status != "pending":
                raise InvalidTimesheetStateError(
                    f"Timesheet {timesheet_id} is '{timesheet.status}', not 'pending'"
                )

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
        """Only a `pending` Timesheet may be deleted -- the same invariant
        `update()` already enforces (no exceptions per field there either).
        An `approved`/`rejected` Timesheet has already been decided;
        deleting it would erase a workflow-decided fact the same way a
        generic field update already isn't permitted to.
        """
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)
            timesheet = await repo.get(timesheet_id)
            if timesheet is None:
                return False

            if timesheet.status != "pending":
                raise InvalidTimesheetStateError(
                    f"Timesheet {timesheet_id} is '{timesheet.status}', not 'pending'"
                )

            deleted = await repo.delete(timesheet_id)
            if deleted:
                await uow.commit()
            return deleted
