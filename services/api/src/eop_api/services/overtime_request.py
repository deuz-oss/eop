import uuid
from collections.abc import Callable, Sequence

from eop_api.models.overtime_request import OvertimeRequest
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.overtime_request import OvertimeRequestRepository
from eop_api.schemas.overtime_request import OvertimeRequestCreate, OvertimeRequestUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by an OvertimeRequest does not exist."""


class InvalidOvertimeTimeRangeError(Exception):
    """Raised when an OvertimeRequest's `end_time` is not after its `start_time`."""


class InvalidOvertimeRequestStateError(Exception):
    """Raised when `update` is attempted on an `OvertimeRequest` whose
    persisted status isn't `pending` (no exceptions per field -- a client
    cannot use a generic field update, including `status`, to reach
    `approved` outside `ApprovalService`). Mirrors
    `ApprovalService.InvalidApprovalStateError`'s precedent for the same
    class of workflow-state invariant.
    """


class OvertimeRequestService:
    """Business logic for `OvertimeRequest`. Owns the transaction boundary via a UoW.

    `OvertimeRequest` is a single employee's request for overtime on one
    date -- not a calculation or payroll record. `ApprovalService`
    (`services/approval.py`) owns approve/reject orchestration -- the
    `pending -> approved`/`pending -> rejected` transitions and their
    authorization -- and is the only path to those transitions.
    `OvertimeRequestService` owns `OvertimeRequest` CRUD and the
    `pending`-only mutation rule enforced here: `create` needs only
    `employee_id` existence and `end_time > start_time`, and always forces
    the new row's `status` to `pending` regardless of any client-supplied
    value; `update` additionally requires the persisted entity's `status` to
    be `pending` (no field is exempt -- including `status` itself, which
    closes the generic-update path as a way to reach `approved` outside
    `ApprovalService`). No audit logging or event/notification dispatch is
    performed by this service.

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

    async def create(self, data: OvertimeRequestCreate) -> OvertimeRequest:
        async with self._uow_factory() as uow:
            repo = OvertimeRequestRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if data.end_time <= data.start_time:
                raise InvalidOvertimeTimeRangeError(
                    f"end_time {data.end_time} is not after start_time {data.start_time}"
                )

            overtime_request = await repo.create(**data.model_dump(), status="pending")
            await uow.commit()
            uow.session.expunge(overtime_request)
            return overtime_request

    async def get(self, overtime_request_id: uuid.UUID) -> OvertimeRequest | None:
        async with self._uow_factory() as uow:
            repo = OvertimeRequestRepository(uow.session)
            overtime_request = await repo.get(overtime_request_id)
            if overtime_request is not None:
                uow.session.expunge(overtime_request)
            return overtime_request

    async def list(self) -> Sequence[OvertimeRequest]:
        async with self._uow_factory() as uow:
            repo = OvertimeRequestRepository(uow.session)
            overtime_requests = await repo.list()
            uow.session.expunge_all()
            return overtime_requests

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[OvertimeRequest]:
        async with self._uow_factory() as uow:
            repo = OvertimeRequestRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, overtime_request_id: uuid.UUID, data: OvertimeRequestUpdate
    ) -> OvertimeRequest | None:
        async with self._uow_factory() as uow:
            repo = OvertimeRequestRepository(uow.session)
            overtime_request = await repo.get(overtime_request_id)
            if overtime_request is None:
                return None

            if overtime_request.status != "pending":
                raise InvalidOvertimeRequestStateError(
                    f"OvertimeRequest {overtime_request_id} is "
                    f"'{overtime_request.status}', not 'pending'"
                )

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            start_time = values.get("start_time", overtime_request.start_time)
            end_time = values.get("end_time", overtime_request.end_time)

            if end_time <= start_time:
                raise InvalidOvertimeTimeRangeError(
                    f"end_time {end_time} is not after start_time {start_time}"
                )

            updated = await repo.update(overtime_request_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, overtime_request_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = OvertimeRequestRepository(uow.session)
            deleted = await repo.delete(overtime_request_id)
            if deleted:
                await uow.commit()
            return deleted
