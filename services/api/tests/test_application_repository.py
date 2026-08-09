import uuid
from collections.abc import AsyncGenerator
from datetime import date

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
from eop_api.repositories.application import ApplicationRepository
from eop_api.repositories.candidate import CandidateRepository
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.job_requisition import JobRequisitionRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository

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
def repo(session: AsyncSession) -> ApplicationRepository:
    return ApplicationRepository(session)


@pytest.fixture
async def candidate_id(session: AsyncSession) -> uuid.UUID:
    candidate = await CandidateRepository(session).create(
        first_name="Ada", last_name="Lovelace", full_name="Ada Lovelace", email="ada@example.com"
    )
    return candidate.id


@pytest.fixture
async def job_requisition_id(session: AsyncSession) -> uuid.UUID:
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
    job_requisition = await JobRequisitionRepository(session).create(
        code="REQ-1",
        title="Backend Engineer",
        organization_id=organization.id,
        department_id=department.id,
        position_id=position.id,
        status="open",
    )
    return job_requisition.id


async def test_create_and_get(
    repo: ApplicationRepository, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await repo.create(
        candidate_id=candidate_id,
        job_requisition_id=job_requisition_id,
        status="applied",
        applied_date=date(2026, 1, 1),
    )

    fetched = await repo.get(application.id)

    assert fetched is not None
    assert fetched.candidate_id == candidate_id
    assert fetched.job_requisition_id == job_requisition_id
    assert fetched.status == "applied"


async def test_get_missing_returns_none(repo: ApplicationRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_get_by_candidate_and_requisition(
    repo: ApplicationRepository, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await repo.create(
        candidate_id=candidate_id,
        job_requisition_id=job_requisition_id,
        status="applied",
        applied_date=date(2026, 1, 1),
    )

    found = await repo.get_by_candidate_and_requisition(candidate_id, job_requisition_id)

    assert found is not None
    assert found.id == application.id
    assert await repo.get_by_candidate_and_requisition(uuid.uuid4(), job_requisition_id) is None


async def test_update_existing(
    repo: ApplicationRepository, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await repo.create(
        candidate_id=candidate_id,
        job_requisition_id=job_requisition_id,
        status="applied",
        applied_date=date(2026, 1, 1),
    )

    updated = await repo.update(application.id, status="interviewing")

    assert updated is not None
    assert updated.status == "interviewing"


async def test_delete_existing(
    repo: ApplicationRepository, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
):
    application = await repo.create(
        candidate_id=candidate_id,
        job_requisition_id=job_requisition_id,
        status="applied",
        applied_date=date(2026, 1, 1),
    )

    deleted = await repo.delete(application.id)

    assert deleted is True
    assert await repo.get(application.id) is None
