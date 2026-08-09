import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime

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
from eop_api.repositories.interview import InterviewRepository
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
def repo(session: AsyncSession) -> InterviewRepository:
    return InterviewRepository(session)


@pytest.fixture
async def application_id(session: AsyncSession) -> uuid.UUID:
    candidate = await CandidateRepository(session).create(
        first_name="Ada", last_name="Lovelace", full_name="Ada Lovelace", email="ada@example.com"
    )
    organization = await OrganizationRepository(session).create(name="Acme Corp")
    department = await DepartmentRepository(session).create(
        organization_id=organization.id, code="ENG", name="Engineering"
    )
    position = await PositionRepository(session).create(
        organization_id=organization.id, department_id=department.id, code="ENG-1", name="Engineer"
    )
    job_requisition = await JobRequisitionRepository(session).create(
        code="REQ-1",
        title="Backend Engineer",
        organization_id=organization.id,
        department_id=department.id,
        position_id=position.id,
        status="open",
    )
    application = await ApplicationRepository(session).create(
        candidate_id=candidate.id,
        job_requisition_id=job_requisition.id,
        status="applied",
        applied_date=date(2026, 1, 1),
    )
    return application.id


async def test_create_and_get(repo: InterviewRepository, application_id: uuid.UUID):
    interview = await repo.create(
        application_id=application_id,
        scheduled_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
        notes="First round",
    )

    fetched = await repo.get(interview.id)

    assert fetched is not None
    assert fetched.application_id == application_id
    assert fetched.notes == "First round"


async def test_get_missing_returns_none(repo: InterviewRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_multiple_interviews_per_application_allowed(
    repo: InterviewRepository, application_id: uuid.UUID
):
    first = await repo.create(
        application_id=application_id,
        scheduled_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )
    second = await repo.create(
        application_id=application_id,
        scheduled_at=datetime(2026, 2, 8, 10, 0, tzinfo=UTC),
    )

    assert first.id != second.id


async def test_update_existing(repo: InterviewRepository, application_id: uuid.UUID):
    interview = await repo.create(
        application_id=application_id,
        scheduled_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )

    updated = await repo.update(interview.id, notes="Rescheduled")

    assert updated is not None
    assert updated.notes == "Rescheduled"


async def test_delete_existing(repo: InterviewRepository, application_id: uuid.UUID):
    interview = await repo.create(
        application_id=application_id,
        scheduled_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )

    deleted = await repo.delete(interview.id)

    assert deleted is True
    assert await repo.get(interview.id) is None


async def test_paginate_filters_by_application_id(
    repo: InterviewRepository, application_id: uuid.UUID
):
    from eop_api.schemas.search import FilterParams

    await repo.create(
        application_id=application_id,
        scheduled_at=datetime(2026, 2, 1, 10, 0, tzinfo=UTC),
    )

    page = await repo.paginate(filters=FilterParams(values={"application_id": application_id}))

    assert page.total == 1

    page_other = await repo.paginate(filters=FilterParams(values={"application_id": uuid.uuid4()}))
    assert page_other.total == 0
