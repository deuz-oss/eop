import uuid
from collections.abc import Callable, Sequence

from eop_api.models.kpi import Kpi
from eop_api.repositories.kpi import KpiRepository
from eop_api.schemas.kpi import KpiCreate, KpiUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateKpiCodeError(Exception):
    """Raised when a KPI code is already in use."""


class KpiService:
    """Business logic for `Kpi`. Owns the transaction boundary via a UoW.

    Master-data-shaped CRUD, mirroring `StoreTypeService`'s structure
    exactly: a `code` uniqueness check, no other validation. `Kpi` is
    definition-only reference data -- no target, achievement, calculation,
    or lifecycle of any kind (`docs/architecture/capabilities/performance/
    kpi-iteration-1-scope-and-implementation-plan.md`).

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: KpiCreate) -> Kpi:
        async with self._uow_factory() as uow:
            repo = KpiRepository(uow.session)

            if await repo.get_by_code(data.code) is not None:
                raise DuplicateKpiCodeError(data.code)

            kpi = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(kpi)
            return kpi

    async def get(self, kpi_id: uuid.UUID) -> Kpi | None:
        async with self._uow_factory() as uow:
            repo = KpiRepository(uow.session)
            kpi = await repo.get(kpi_id)
            if kpi is not None:
                uow.session.expunge(kpi)
            return kpi

    async def list(self) -> Sequence[Kpi]:
        async with self._uow_factory() as uow:
            repo = KpiRepository(uow.session)
            kpis = await repo.list()
            uow.session.expunge_all()
            return kpis

    async def list_paginated(
        self, pagination: PaginationParams, search: SearchParams | None = None
    ) -> Page[Kpi]:
        async with self._uow_factory() as uow:
            repo = KpiRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search
            )
            uow.session.expunge_all()
            return page

    async def update(self, kpi_id: uuid.UUID, data: KpiUpdate) -> Kpi | None:
        async with self._uow_factory() as uow:
            repo = KpiRepository(uow.session)
            kpi = await repo.get(kpi_id)
            if kpi is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != kpi_id:
                    raise DuplicateKpiCodeError(values["code"])

            updated = await repo.update(kpi_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, kpi_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = KpiRepository(uow.session)
            deleted = await repo.delete(kpi_id)
            if deleted:
                await uow.commit()
            return deleted
