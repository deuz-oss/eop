import uuid
from collections.abc import Callable, Sequence

from eop_api.models.leave_request import LeaveRequest
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.leave_request import LeaveRequestRepository
from eop_api.schemas.leave_request import LeaveRequestCreate, LeaveRequestUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a LeaveRequest does not exist."""


class InvalidLeaveDateRangeError(Exception):
    """Raised when a LeaveRequest's `end_date` is earlier than its `start_date`."""


class LeaveRequestService:
    """Business logic for `LeaveRequest`. Owns the transaction boundary via a UoW.

    `LeaveRequest` is a single employee's request for a dated span -- not a
    balance, entitlement, or approval-workflow record. Only the existence of
    `employee_id` and `start_date <= end_date` are validated here. Overlap
    detection, duplicate detection, leave balance/entitlement, weekends,
    holidays, half-days, payroll rules, attendance reconciliation, employment
    status validation, and approval validation are all explicitly out of
    scope for this module and belong to future PRs. `status` is stored only;
    no transition validation is performed.

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

    async def create(self, data: LeaveRequestCreate) -> LeaveRequest:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if data.end_date < data.start_date:
                raise InvalidLeaveDateRangeError(
                    f"end_date {data.end_date} is before start_date {data.start_date}"
                )

            leave_request = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(leave_request)
            return leave_request

    async def get(self, leave_request_id: uuid.UUID) -> LeaveRequest | None:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            leave_request = await repo.get(leave_request_id)
            if leave_request is not None:
                uow.session.expunge(leave_request)
            return leave_request

    async def list(self) -> Sequence[LeaveRequest]:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            leave_requests = await repo.list()
            uow.session.expunge_all()
            return leave_requests

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[LeaveRequest]:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, leave_request_id: uuid.UUID, data: LeaveRequestUpdate
    ) -> LeaveRequest | None:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            leave_request = await repo.get(leave_request_id)
            if leave_request is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            start_date = values.get("start_date", leave_request.start_date)
            end_date = values.get("end_date", leave_request.end_date)

            if end_date < start_date:
                raise InvalidLeaveDateRangeError(
                    f"end_date {end_date} is before start_date {start_date}"
                )

            updated = await repo.update(leave_request_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, leave_request_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            deleted = await repo.delete(leave_request_id)
            if deleted:
                await uow.commit()
            return deleted
