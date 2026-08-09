import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.job_requisition import JobRequisitionRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.schemas.search import SearchParams

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    conn = await engine.connect()
    trans = await conn.begin()
    try:
        yield conn
    finally:
        await trans.rollback()
        await conn.close()
        await engine.dispose()


@pytest.fixture
def session(connection: AsyncConnection) -> AsyncSession:
    return async_sessionmaker(bind=connection, expire_on_commit=False)()


@pytest.fixture
def repo(session: AsyncSession) -> JobRequisitionRepository:
    return JobRequisitionRepository(session)


@pytest.fixture
async def ids(session: AsyncSession) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
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
    return organization.id, department.id, position.id


async def test_create_and_get(
    repo: JobRequisitionRepository, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    organization_id, department_id, position_id = ids
    job_requisition = await repo.create(
        code="REQ-1",
        title="Backend Engineer",
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        status="open",
    )

    fetched = await repo.get(job_requisition.id)

    assert fetched is not None
    assert fetched.code == "REQ-1"
    assert fetched.title == "Backend Engineer"
    assert fetched.status == "open"
    assert fetched.description is None


async def test_get_missing_returns_none(repo: JobRequisitionRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_get_by_code(
    repo: JobRequisitionRepository, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    organization_id, department_id, position_id = ids
    job_requisition = await repo.create(
        code="REQ-1",
        title="Backend Engineer",
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        status="open",
    )

    found = await repo.get_by_code("REQ-1")

    assert found is not None
    assert found.id == job_requisition.id
    assert await repo.get_by_code("missing") is None


async def test_update_existing(
    repo: JobRequisitionRepository, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    organization_id, department_id, position_id = ids
    job_requisition = await repo.create(
        code="REQ-1",
        title="Before",
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        status="open",
    )

    updated = await repo.update(job_requisition.id, title="After")

    assert updated is not None
    assert updated.title == "After"


async def test_delete_existing(
    repo: JobRequisitionRepository, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    organization_id, department_id, position_id = ids
    job_requisition = await repo.create(
        code="REQ-1",
        title="Backend Engineer",
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        status="open",
    )

    deleted = await repo.delete(job_requisition.id)

    assert deleted is True
    assert await repo.get(job_requisition.id) is None


async def test_paginate_search_by_title(
    repo: JobRequisitionRepository, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    organization_id, department_id, position_id = ids
    await repo.create(
        code="REQ-1",
        title="Backend Engineer",
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        status="open",
    )
    await repo.create(
        code="REQ-2",
        title="Product Manager",
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        status="open",
    )

    page = await repo.paginate(search=SearchParams(q="backend"))

    assert page.total == 1
    assert page.items[0].title == "Backend Engineer"


async def test_paginate_filters_by_status(
    repo: JobRequisitionRepository, ids: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
):
    from eop_api.schemas.search import FilterParams

    organization_id, department_id, position_id = ids
    await repo.create(
        code="REQ-1",
        title="Backend Engineer",
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        status="open",
    )
    await repo.create(
        code="REQ-2",
        title="Product Manager",
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        status="closed",
    )

    page = await repo.paginate(filters=FilterParams(values={"status": "closed"}))

    assert page.total == 1
    assert page.items[0].title == "Product Manager"
