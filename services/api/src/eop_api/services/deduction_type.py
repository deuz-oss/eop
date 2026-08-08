import uuid
from collections.abc import Callable, Sequence

from eop_api.models.deduction_type import DeductionType
from eop_api.repositories.deduction_type import DeductionTypeRepository
from eop_api.schemas.deduction_type import DeductionTypeCreate, DeductionTypeUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateDeductionTypeCodeError(Exception):
    """Raised when a deduction type code is already in use."""


class DeductionTypeService:
    """Business logic for `DeductionType`. Owns the transaction boundary via a UoW.

    Mirrors `EmploymentTypeService` exactly -- global reference data, no
    hierarchy, no owner. No public write API route is exposed for this
    service in v1 (`implementation-plan.md` §10.4) -- it is fully built and
    tested, used internally/seeded directly until an admin authorization
    concept exists (`TECHNICAL_DEBT_REGISTER.md` TD-004).
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: DeductionTypeCreate) -> DeductionType:
        async with self._uow_factory() as uow:
            repo = DeductionTypeRepository(uow.session)

            if await repo.get_by_code(data.code):
                raise DuplicateDeductionTypeCodeError(data.code)

            deduction_type = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(deduction_type)
            return deduction_type

    async def get(self, deduction_type_id: uuid.UUID) -> DeductionType | None:
        async with self._uow_factory() as uow:
            repo = DeductionTypeRepository(uow.session)
            deduction_type = await repo.get(deduction_type_id)
            if deduction_type is not None:
                uow.session.expunge(deduction_type)
            return deduction_type

    async def list(self) -> Sequence[DeductionType]:
        async with self._uow_factory() as uow:
            repo = DeductionTypeRepository(uow.session)
            deduction_types = await repo.list()
            uow.session.expunge_all()
            return deduction_types

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[DeductionType]:
        async with self._uow_factory() as uow:
            repo = DeductionTypeRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, deduction_type_id: uuid.UUID, data: DeductionTypeUpdate
    ) -> DeductionType | None:
        async with self._uow_factory() as uow:
            repo = DeductionTypeRepository(uow.session)
            deduction_type = await repo.get(deduction_type_id)
            if deduction_type is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != deduction_type_id:
                    raise DuplicateDeductionTypeCodeError(values["code"])

            updated = await repo.update(deduction_type_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, deduction_type_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = DeductionTypeRepository(uow.session)
            deleted = await repo.delete(deduction_type_id)
            if deleted:
                await uow.commit()
            return deleted
