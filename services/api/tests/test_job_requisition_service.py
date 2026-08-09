import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.schemas.job_requisition import JobRequisitionCreate, JobRequisitionUpdate
from eop_api.services.job_requisition import (
    DepartmentNotFoundError,
    DuplicateJobRequisitionCodeError,
    JobRequisitionService,
    OrganizationNotFoundError,
    PositionNotFoundError,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE organizations CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> JobRequisitionService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return JobRequisitionService(uow_factory)


@pytest.fixture
async def ids(
    session_factory: Callable[[], AsyncSession],
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Acme Corp")
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="ENG", name="Engineering"
        )
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="ENG-1",
            name="Engineer",
        )
        await session.commit()
        return organization.id, department.id, position.id


def _create(
    ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID], code: str = "REQ-1", **overrides
) -> JobRequisitionCreate:
    organization_id, department_id, position_id = ids
    values = {
        "code": code,
        "title": "Backend Engineer",
        "organization_id": organization_id,
        "department_id": department_id,
        "position_id": position_id,
        "status": "open",
    }
    values.update(overrides)
    return JobRequisitionCreate(**values)


async def test_create_and_get(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    job_requisition = await service.create(_create(ids))

    fetched = await service.get(job_requisition.id)

    assert fetched is not None
    assert fetched.code == "REQ-1"
    assert fetched.status == "open"


async def test_create_rejects_duplicate_code(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    await service.create(_create(ids, code="REQ-1"))

    with pytest.raises(DuplicateJobRequisitionCodeError):
        await service.create(_create(ids, code="REQ-1", title="Other"))


async def test_create_rejects_missing_organization(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    with pytest.raises(OrganizationNotFoundError):
        await service.create(_create(ids, organization_id=uuid.uuid4()))


async def test_create_rejects_missing_department(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    with pytest.raises(DepartmentNotFoundError):
        await service.create(_create(ids, department_id=uuid.uuid4()))


async def test_create_rejects_missing_position(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    with pytest.raises(PositionNotFoundError):
        await service.create(_create(ids, position_id=uuid.uuid4()))


async def test_get_missing_returns_none(service: JobRequisitionService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    await service.create(_create(ids, code="REQ-1"))
    await service.create(_create(ids, code="REQ-2", title="Product Manager"))

    items = await service.list()

    assert {"Backend Engineer", "Product Manager"}.issubset({item.title for item in items})


async def test_update_existing(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    job_requisition = await service.create(_create(ids))

    updated = await service.update(job_requisition.id, JobRequisitionUpdate(status="closed"))

    assert updated is not None
    assert updated.status == "closed"


async def test_update_missing_returns_none(service: JobRequisitionService):
    assert await service.update(uuid.uuid4(), JobRequisitionUpdate(status="closed")) is None


async def test_update_rejects_duplicate_code(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    await service.create(_create(ids, code="REQ-1"))
    other = await service.create(_create(ids, code="REQ-2", title="Product Manager"))

    with pytest.raises(DuplicateJobRequisitionCodeError):
        await service.update(other.id, JobRequisitionUpdate(code="REQ-1"))


async def test_delete_existing(
    service: JobRequisitionService, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    job_requisition = await service.create(_create(ids))

    deleted = await service.delete(job_requisition.id)

    assert deleted is True
    assert await service.get(job_requisition.id) is None


async def test_delete_missing_returns_false(service: JobRequisitionService):
    assert await service.delete(uuid.uuid4()) is False
