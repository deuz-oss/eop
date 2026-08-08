import uuid
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any

from eop_api.models.work_schedule import WorkSchedule
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.work_schedule import WorkScheduleRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.schemas.work_schedule import WorkScheduleCreate, WorkScheduleUpdate
from eop_api.services.authorization import AuthorizationService
from eop_api.services.authorization_request import AuthorizationRequest
from eop_api.services.effective_dating_evaluator import EffectiveDatingEvaluator
from eop_api.services.employee_context import RequestContext
from eop_api.services.work_schedule_authorization import WorkScheduleAuthorizationEvaluator
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a WorkSchedule does not exist."""


class ShiftNotFoundError(Exception):
    """Raised when the Shift referenced by a WorkSchedule does not exist."""


class CorrectionTargetNotFoundError(Exception):
    """Raised when `WorkScheduleCreate.corrects_id` does not reference an
    existing WorkSchedule row."""


class CorrectionTargetEmployeeMismatchError(Exception):
    """Raised when `WorkScheduleCreate.corrects_id` references a WorkSchedule
    row belonging to a different employee than `WorkScheduleCreate.employee_id`."""


class OverlappingWorkSchedulePeriodError(Exception):
    """Raised when a new WorkSchedule row's effective period overlaps an
    existing row for the same employee.

    A correction row (`corrects_id` set) is exempt from this check only
    against the exact row it corrects -- see
    `WorkScheduleRepository.find_overlapping_periods`'s `exclude_id`.
    """


class WorkScheduleAuthorizationDeniedError(Exception):
    """Raised when the Work Schedule Authorization Policy (Owner Only,
    `docs/architecture/capabilities/work-schedule/
    iteration-1-implementation-plan.md` §1 #4) denies a create/get/update/
    delete call -- i.e. `AuthorizationDecision.allowed` is `False`.
    """


class WorkScheduleService:
    """Business logic for `WorkSchedule`. Owns the transaction boundary via a UoW.

    Mirrors `CompensationService`'s structure and policy directly
    (`iteration-1-implementation-plan.md` §5): effective-dated, multiple
    rows per employee, overlap and correction policy identical in shape
    (overlap rejected except against the exact row a correction corrects;
    `corrects_id` records a compensating correction; the corrected row is
    never mutated).

    `update()` is intentionally narrow: only `is_active` may be changed.
    Changing `shift_id`, any `works_*` day flag, or the effective period of
    an existing row would mutate a historical business fact in place.
    Recording a new schedule state, or a correction, uses `create()`.

    Every `create`/`get`/`update`/`delete` call is gated by the Work
    Schedule Authorization Policy (Owner Only), delegated to
    `AuthorizationService`/`WorkScheduleAuthorizationEvaluator` via
    `_authorize`. `list`/`list_paginated` are scoped to the caller's own
    `employee_id` rather than authorized per-item, mirroring
    `CompensationService`.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory
        self._evaluator = EffectiveDatingEvaluator()

    async def create(
        self, data: WorkScheduleCreate, request_context: RequestContext
    ) -> WorkSchedule:
        async with self._uow_factory() as uow:
            repo = WorkScheduleRepository(uow.session)

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if not await ShiftRepository(uow.session).exists(data.shift_id):
                raise ShiftNotFoundError(str(data.shift_id))

            await self._authorize(data, request_context)

            if data.corrects_id is not None:
                target = await repo.get(data.corrects_id)
                if target is None:
                    raise CorrectionTargetNotFoundError(str(data.corrects_id))
                if target.employee_id != data.employee_id:
                    raise CorrectionTargetEmployeeMismatchError(str(data.corrects_id))

            overlapping = await repo.find_overlapping_periods(
                data.employee_id,
                data.effective_from,
                data.effective_to,
                exclude_id=data.corrects_id,
            )
            if overlapping:
                raise OverlappingWorkSchedulePeriodError(
                    f"Work schedule period for employee {data.employee_id} "
                    "overlaps an existing period"
                )

            work_schedule = await repo.create(
                employee_id=data.employee_id,
                shift_id=data.shift_id,
                works_monday=data.works_monday,
                works_tuesday=data.works_tuesday,
                works_wednesday=data.works_wednesday,
                works_thursday=data.works_thursday,
                works_friday=data.works_friday,
                works_saturday=data.works_saturday,
                works_sunday=data.works_sunday,
                effective_from=data.effective_from,
                effective_to=data.effective_to,
                corrects_id=data.corrects_id,
            )
            await uow.commit()
            uow.session.expunge(work_schedule)
            return work_schedule

    async def get(
        self, work_schedule_id: uuid.UUID, request_context: RequestContext
    ) -> WorkSchedule | None:
        async with self._uow_factory() as uow:
            repo = WorkScheduleRepository(uow.session)
            work_schedule = await repo.get(work_schedule_id)
            if work_schedule is None:
                return None
            await self._authorize(work_schedule, request_context)
            uow.session.expunge(work_schedule)
            return work_schedule

    async def get_by_employee(
        self,
        employee_id: uuid.UUID,
        request_context: RequestContext | None = None,
        as_of_date: date | None = None,
    ) -> WorkSchedule | None:
        """The `WorkSchedule` row effective for `employee_id` as of `as_of_date`.

        `as_of_date` defaults to today. Correction precedence is applied
        before the generic evaluator resolves the candidate set, mirroring
        `CompensationService.get_by_employee` exactly.
        """
        async with self._uow_factory() as uow:
            repo = WorkScheduleRepository(uow.session)
            resolved_date = as_of_date if as_of_date is not None else date.today()
            candidates = await repo.list_effective_as_of(employee_id, resolved_date)
            resolvable = self._exclude_corrected_targets(candidates)
            work_schedule = self._evaluator.resolve(resolvable, resolved_date)
            if work_schedule is None:
                return None
            if request_context is not None:
                await self._authorize(work_schedule, request_context)
            uow.session.expunge(work_schedule)
            return work_schedule

    @staticmethod
    def _exclude_corrected_targets(rows: Sequence[WorkSchedule]) -> list[WorkSchedule]:
        """Correction-precedence policy, mirroring `CompensationService`'s
        identical method: when a correction row and the row it corrects are
        both present in `rows`, the correction wins.
        """
        corrected_ids = {row.corrects_id for row in rows if row.corrects_id is not None}
        return [row for row in rows if row.id not in corrected_ids]

    async def list_history(self, request_context: RequestContext) -> Sequence[WorkSchedule]:
        """Every historical `WorkSchedule` row for the caller's own employee, oldest first."""
        async with self._uow_factory() as uow:
            repo = WorkScheduleRepository(uow.session)
            employee_id = request_context.employee_context.employee.id
            history = await repo.list_by_employee_id(employee_id)
            uow.session.expunge_all()
            return history

    async def list(self, request_context: RequestContext) -> Sequence[WorkSchedule]:
        """WorkSchedule records owned by the caller's own `employee_id`."""
        async with self._uow_factory() as uow:
            repo = WorkScheduleRepository(uow.session)
            work_schedules = await repo.list()
            current_employee_id = request_context.employee_context.employee.id
            owned = [w for w in work_schedules if w.employee_id == current_employee_id]
            uow.session.expunge_all()
            return owned

    async def list_paginated(
        self,
        request_context: RequestContext,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[WorkSchedule]:
        """WorkSchedule records owned by the caller's own `employee_id`, paginated.

        `employee_id` is forced to the caller's own resolved employee id,
        overriding any client-supplied value in `filters`, mirroring
        `CompensationService.list_paginated`.
        """
        async with self._uow_factory() as uow:
            repo = WorkScheduleRepository(uow.session)
            scoped_values = dict(filters.values) if filters else {}
            scoped_values["employee_id"] = request_context.employee_context.employee.id
            scoped_filters = FilterParams(values=scoped_values)
            page = await repo.paginate(
                offset=pagination.offset,
                limit=pagination.limit,
                search=search,
                filters=scoped_filters,
            )
            uow.session.expunge_all()
            return page

    async def update(
        self,
        work_schedule_id: uuid.UUID,
        data: WorkScheduleUpdate,
        request_context: RequestContext,
    ) -> WorkSchedule | None:
        """Toggles `is_active` on an existing row. Nothing else is updatable."""
        async with self._uow_factory() as uow:
            repo = WorkScheduleRepository(uow.session)
            work_schedule = await repo.get(work_schedule_id)
            if work_schedule is None:
                return None

            await self._authorize(work_schedule, request_context)

            values = data.model_dump(exclude_unset=True)

            updated = await repo.update(work_schedule_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, work_schedule_id: uuid.UUID, request_context: RequestContext) -> bool:
        async with self._uow_factory() as uow:
            repo = WorkScheduleRepository(uow.session)
            work_schedule = await repo.get(work_schedule_id)
            if work_schedule is None:
                return False

            await self._authorize(work_schedule, request_context)

            deleted = await repo.delete(work_schedule_id)
            if deleted:
                await uow.commit()
            return deleted

    async def _authorize(self, resource: Any, request_context: RequestContext) -> None:
        """Evaluate the Work Schedule Authorization Policy (Owner Only) for `resource`."""
        authorization_request = AuthorizationRequest(context=request_context, resource=resource)
        decision = AuthorizationService(WorkScheduleAuthorizationEvaluator()).authorize(
            authorization_request
        )
        if not decision.allowed:
            raise WorkScheduleAuthorizationDeniedError(
                decision.reason or "Work schedule authorization denied"
            )
