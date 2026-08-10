import uuid
from collections.abc import Callable, Sequence

from eop_api.models.mission import Mission
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.mission import MissionRepository
from eop_api.repositories.store import StoreRepository
from eop_api.schemas.mission import MissionCreate, MissionUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the HrEmployee referenced by a Mission does not exist."""


class StoreNotFoundError(Exception):
    """Raised when the Store referenced by a Mission does not exist."""


class MissionService:
    """Business logic for `Mission`. Owns the transaction boundary via a UoW.

    `Mission` is a single employee-to-store planning/assignment record for
    one date (`docs/architecture/capabilities/mission/
    mission-iteration-1-scope-and-implementation-plan.md`). `create`/
    `update` validate that `employee_id`/`store_id` (when supplied)
    reference existing rows, mirroring `VisitService`'s identical
    existence-check pattern.

    Authorization is Role Based (`RequireRole("admin")`, enforced entirely
    at the API layer via `RequireMissionAdmin`) -- no Owner Only evaluator
    exists for `Mission`, mirroring `TargetService` exactly: this service
    performs no authorization check of its own.

    `update` allows changing all three fields (`employee_id`, `store_id`,
    `scheduled_date`) -- mirrors `VisitUpdate`'s own precedent exactly, not
    `TargetUpdate`'s narrower value-only update, since Mission has no
    separate identity/value split.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository. `update`
    additionally refreshes the entity before expunging it, for the same
    `updated_at` server-side `onupdate` reason documented on
    `VisitService.update`/`TargetService.update`.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: MissionCreate) -> Mission:
        async with self._uow_factory() as uow:
            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            if not await StoreRepository(uow.session).exists(data.store_id):
                raise StoreNotFoundError(str(data.store_id))

            repo = MissionRepository(uow.session)
            mission = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(mission)
            return mission

    async def get(self, mission_id: uuid.UUID) -> Mission | None:
        async with self._uow_factory() as uow:
            repo = MissionRepository(uow.session)
            mission = await repo.get(mission_id)
            if mission is not None:
                uow.session.expunge(mission)
            return mission

    async def list(self) -> Sequence[Mission]:
        async with self._uow_factory() as uow:
            repo = MissionRepository(uow.session)
            missions = await repo.list()
            uow.session.expunge_all()
            return missions

    async def list_paginated(
        self, pagination: PaginationParams, filters: FilterParams | None = None
    ) -> Page[Mission]:
        async with self._uow_factory() as uow:
            repo = MissionRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, mission_id: uuid.UUID, data: MissionUpdate) -> Mission | None:
        async with self._uow_factory() as uow:
            repo = MissionRepository(uow.session)
            mission = await repo.get(mission_id)
            if mission is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "employee_id" in values:
                if not await HrEmployeeRepository(uow.session).exists(values["employee_id"]):
                    raise EmployeeNotFoundError(str(values["employee_id"]))

            if "store_id" in values:
                if not await StoreRepository(uow.session).exists(values["store_id"]):
                    raise StoreNotFoundError(str(values["store_id"]))

            updated = await repo.update(mission_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, mission_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = MissionRepository(uow.session)
            deleted = await repo.delete(mission_id)
            if deleted:
                await uow.commit()
            return deleted
