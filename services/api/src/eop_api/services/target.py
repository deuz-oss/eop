import uuid
from collections.abc import Callable, Sequence

from eop_api.models.target import Target
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.kpi import KpiRepository
from eop_api.repositories.target import TargetRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.schemas.target import TargetCreate, TargetUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class KpiNotFoundError(Exception):
    """Raised when the Kpi referenced by a Target does not exist."""


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Target does not exist."""


class DuplicateTargetError(Exception):
    """Raised when a Target already exists for the same
    employee_id + kpi_id + period_year + period_month.

    Enforced at the database level via `Target`'s composite
    `UniqueConstraint` (`uq_targets_employee_kpi_period`) -- this exception
    surfaces the same refusal as an explicit application error instead of an
    unhandled `IntegrityError`, mirroring `DuplicateSurveyError`'s
    check-then-insert shape.
    """


class TargetService:
    """Business logic for `Target`. Owns the transaction boundary via a UoW.

    `Target` is an employee-scoped KPI goal for one calendar month
    (`docs/architecture/capabilities/performance/
    target-iteration-1-scope-and-implementation-plan.md`). `create()`
    validates that both `kpi_id` and `employee_id` reference existing rows
    and that no Target already exists for the same
    employee/KPI/period-month combination.

    Authorization is Role Based (`RequireRole("admin")`, enforced entirely
    at the API layer via `RequireTargetAdmin`) -- no Owner Only evaluator
    exists for `Target`: `employee_id` is the Target's business scope, not
    its authorization boundary (§8). This service performs no authorization
    check of its own, unlike `VisitService`/`SurveyService`/
    `CompensationService`.

    `update()` only ever changes `goal_value` -- `TargetUpdate` carries no
    other field, so identity/uniqueness fields can never be modified through
    this method.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository. `update`
    additionally refreshes the entity before expunging it, for the same
    `updated_at` server-side `onupdate` reason documented on
    `SurveyService.update`.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: TargetCreate) -> Target:
        async with self._uow_factory() as uow:
            if not await KpiRepository(uow.session).exists(data.kpi_id):
                raise KpiNotFoundError(str(data.kpi_id))

            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            repo = TargetRepository(uow.session)
            existing = await repo.get_by_identity(
                data.employee_id, data.kpi_id, data.period_year, data.period_month
            )
            if existing is not None:
                raise DuplicateTargetError(
                    f"employee_id={data.employee_id} kpi_id={data.kpi_id} "
                    f"period={data.period_year}-{data.period_month:02d}"
                )

            target = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(target)
            return target

    async def get(self, target_id: uuid.UUID) -> Target | None:
        async with self._uow_factory() as uow:
            repo = TargetRepository(uow.session)
            target = await repo.get(target_id)
            if target is not None:
                uow.session.expunge(target)
            return target

    async def list(self) -> Sequence[Target]:
        async with self._uow_factory() as uow:
            repo = TargetRepository(uow.session)
            targets = await repo.list()
            uow.session.expunge_all()
            return targets

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Target]:
        async with self._uow_factory() as uow:
            repo = TargetRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, target_id: uuid.UUID, data: TargetUpdate) -> Target | None:
        async with self._uow_factory() as uow:
            repo = TargetRepository(uow.session)
            target = await repo.get(target_id)
            if target is None:
                return None

            values = data.model_dump(exclude_unset=True)

            updated = await repo.update(target_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, target_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = TargetRepository(uow.session)
            deleted = await repo.delete(target_id)
            if deleted:
                await uow.commit()
            return deleted
