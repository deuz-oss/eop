import uuid
from collections.abc import Callable, Sequence

from eop_api.models.payroll_run import PayrollRun
from eop_api.repositories.payroll_run import PayrollRunRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.payroll_run import PayrollRunCreate, PayrollRunUpdate
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicatePayrollRunCodeError(Exception):
    """Raised when a payroll run code is already in use."""


class PayrollRunService:
    """Business logic for `PayrollRun`. Owns the transaction boundary via a UoW.

    `PayrollRun` is Payroll's aggregate root for iteration 1 (structural
    scaffolding only, per
    `docs/architecture/capabilities/payroll/implementation-plan.md`) -- plain
    CRUD plus a `code` uniqueness check, the same shape as
    `EmploymentTypeService`. No computation, no orchestration, no
    authorization, no cross-capability access.

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

    async def create(self, data: PayrollRunCreate) -> PayrollRun:
        async with self._uow_factory() as uow:
            repo = PayrollRunRepository(uow.session)

            if await repo.get_by_code(data.code):
                raise DuplicatePayrollRunCodeError(data.code)

            payroll_run = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(payroll_run)
            return payroll_run

    async def get(self, payroll_run_id: uuid.UUID) -> PayrollRun | None:
        async with self._uow_factory() as uow:
            repo = PayrollRunRepository(uow.session)
            payroll_run = await repo.get(payroll_run_id)
            if payroll_run is not None:
                uow.session.expunge(payroll_run)
            return payroll_run

    async def list(self) -> Sequence[PayrollRun]:
        async with self._uow_factory() as uow:
            repo = PayrollRunRepository(uow.session)
            payroll_runs = await repo.list()
            uow.session.expunge_all()
            return payroll_runs

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[PayrollRun]:
        async with self._uow_factory() as uow:
            repo = PayrollRunRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, payroll_run_id: uuid.UUID, data: PayrollRunUpdate
    ) -> PayrollRun | None:
        async with self._uow_factory() as uow:
            repo = PayrollRunRepository(uow.session)
            payroll_run = await repo.get(payroll_run_id)
            if payroll_run is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != payroll_run_id:
                    raise DuplicatePayrollRunCodeError(values["code"])

            updated = await repo.update(payroll_run_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, payroll_run_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = PayrollRunRepository(uow.session)
            deleted = await repo.delete(payroll_run_id)
            if deleted:
                await uow.commit()
            return deleted
