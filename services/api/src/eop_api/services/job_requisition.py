import uuid
from collections.abc import Callable, Sequence

from eop_api.models.job_requisition import JobRequisition
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.job_requisition import JobRequisitionRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.schemas.job_requisition import JobRequisitionCreate, JobRequisitionUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class DuplicateJobRequisitionCodeError(Exception):
    """Raised when a job requisition code is already in use."""


class OrganizationNotFoundError(Exception):
    """Raised when the organization referenced by a JobRequisition does not exist."""


class DepartmentNotFoundError(Exception):
    """Raised when the department referenced by a JobRequisition does not exist."""


class PositionNotFoundError(Exception):
    """Raised when the position referenced by a JobRequisition does not exist."""


class JobRequisitionService:
    """Business logic for `JobRequisition`. Owns the transaction boundary via a UoW.

    Mirrors `ShiftService`'s structure exactly -- master-data-shaped CRUD,
    no dedicated authorization evaluator (`CurrentUser`-only at the API
    layer), plain `code` uniqueness. `status` is not validated against an
    enum or state machine here, per
    `docs/architecture/capabilities/recruitment/
    iteration-1-scope-and-implementation-plan.md` §2 -- no pipeline model
    is decided or invented in this iteration.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: JobRequisitionCreate) -> JobRequisition:
        async with self._uow_factory() as uow:
            repo = JobRequisitionRepository(uow.session)

            if await repo.get_by_code(data.code):
                raise DuplicateJobRequisitionCodeError(data.code)

            if not await OrganizationRepository(uow.session).exists(data.organization_id):
                raise OrganizationNotFoundError(str(data.organization_id))

            if not await DepartmentRepository(uow.session).exists(data.department_id):
                raise DepartmentNotFoundError(str(data.department_id))

            if not await PositionRepository(uow.session).exists(data.position_id):
                raise PositionNotFoundError(str(data.position_id))

            job_requisition = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(job_requisition)
            return job_requisition

    async def get(self, job_requisition_id: uuid.UUID) -> JobRequisition | None:
        async with self._uow_factory() as uow:
            repo = JobRequisitionRepository(uow.session)
            job_requisition = await repo.get(job_requisition_id)
            if job_requisition is not None:
                uow.session.expunge(job_requisition)
            return job_requisition

    async def list(self) -> Sequence[JobRequisition]:
        async with self._uow_factory() as uow:
            repo = JobRequisitionRepository(uow.session)
            job_requisitions = await repo.list()
            uow.session.expunge_all()
            return job_requisitions

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[JobRequisition]:
        async with self._uow_factory() as uow:
            repo = JobRequisitionRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, job_requisition_id: uuid.UUID, data: JobRequisitionUpdate
    ) -> JobRequisition | None:
        async with self._uow_factory() as uow:
            repo = JobRequisitionRepository(uow.session)
            job_requisition = await repo.get(job_requisition_id)
            if job_requisition is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "code" in values:
                existing = await repo.get_by_code(values["code"])
                if existing is not None and existing.id != job_requisition_id:
                    raise DuplicateJobRequisitionCodeError(values["code"])

            if "organization_id" in values and not await OrganizationRepository(uow.session).exists(
                values["organization_id"]
            ):
                raise OrganizationNotFoundError(str(values["organization_id"]))

            if "department_id" in values and not await DepartmentRepository(uow.session).exists(
                values["department_id"]
            ):
                raise DepartmentNotFoundError(str(values["department_id"]))

            if "position_id" in values and not await PositionRepository(uow.session).exists(
                values["position_id"]
            ):
                raise PositionNotFoundError(str(values["position_id"]))

            updated = await repo.update(job_requisition_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, job_requisition_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = JobRequisitionRepository(uow.session)
            deleted = await repo.delete(job_requisition_id)
            if deleted:
                await uow.commit()
            return deleted
