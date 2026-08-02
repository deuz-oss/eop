import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.schemas.job_grade import JobGradeCreate, JobGradeUpdate
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.services.job_grade import (
    DuplicateJobGradeCodeError,
    DuplicateJobGradeLevelError,
    JobGradeService,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) `job_grades` table.

    Unlike the repository tests, the service commits internally (it owns the
    transaction boundary), so rows are truncated after each test instead of
    relying on a rolled-back transaction.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    try:
        yield factory
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE job_grades CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> JobGradeService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return JobGradeService(uow_factory)


async def test_create_and_get(service: JobGradeService):
    job_grade = await service.create(JobGradeCreate(code="L1", name="Junior", level=1))

    fetched = await service.get(job_grade.id)

    assert fetched is not None
    assert fetched.code == "L1"
    assert fetched.name == "Junior"
    assert fetched.level == 1


async def test_create_rejects_duplicate_code(service: JobGradeService):
    await service.create(JobGradeCreate(code="L1", name="Junior", level=1))

    with pytest.raises(DuplicateJobGradeCodeError):
        await service.create(JobGradeCreate(code="L1", name="Junior Two", level=2))


async def test_create_rejects_duplicate_level(service: JobGradeService):
    await service.create(JobGradeCreate(code="L1", name="Junior", level=1))

    with pytest.raises(DuplicateJobGradeLevelError):
        await service.create(JobGradeCreate(code="L2", name="Junior Two", level=1))


async def test_get_missing_returns_none(service: JobGradeService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: JobGradeService):
    await service.create(JobGradeCreate(code="L1", name="Junior", level=1))
    await service.create(JobGradeCreate(code="L2", name="Mid", level=2))

    items = await service.list()

    assert {"Junior", "Mid"}.issubset({item.name for item in items})


async def test_update_existing(service: JobGradeService):
    job_grade = await service.create(JobGradeCreate(code="L1", name="Before", level=1))

    updated = await service.update(job_grade.id, JobGradeUpdate(name="After"))

    assert updated is not None
    assert updated.name == "After"


async def test_update_missing_returns_none(service: JobGradeService):
    assert await service.update(uuid.uuid4(), JobGradeUpdate(name="After")) is None


async def test_update_rejects_duplicate_code(service: JobGradeService):
    await service.create(JobGradeCreate(code="L1", name="Junior", level=1))
    other = await service.create(JobGradeCreate(code="L2", name="Mid", level=2))

    with pytest.raises(DuplicateJobGradeCodeError):
        await service.update(other.id, JobGradeUpdate(code="L1"))


async def test_update_rejects_duplicate_level(service: JobGradeService):
    await service.create(JobGradeCreate(code="L1", name="Junior", level=1))
    other = await service.create(JobGradeCreate(code="L2", name="Mid", level=2))

    with pytest.raises(DuplicateJobGradeLevelError):
        await service.update(other.id, JobGradeUpdate(level=1))


async def test_update_allows_unchanged_code_and_level(service: JobGradeService):
    job_grade = await service.create(JobGradeCreate(code="L1", name="Junior", level=1))

    updated = await service.update(
        job_grade.id, JobGradeUpdate(code="L1", level=1, name="Junior Renamed")
    )

    assert updated is not None
    assert updated.name == "Junior Renamed"


async def test_delete_existing(service: JobGradeService):
    job_grade = await service.create(JobGradeCreate(code="L1", name="To Delete", level=1))

    deleted = await service.delete(job_grade.id)

    assert deleted is True
    assert await service.get(job_grade.id) is None


async def test_delete_missing_returns_false(service: JobGradeService):
    assert await service.delete(uuid.uuid4()) is False


async def test_list_paginated_passes_through_offset_and_limit(service: JobGradeService):
    for i in range(5):
        await service.create(JobGradeCreate(code=f"L{i}", name=f"Grade {i}", level=i))

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: JobGradeService):
    await service.create(JobGradeCreate(code="L1", name="Junior Engineer", level=1))
    await service.create(JobGradeCreate(code="L2", name="Senior Manager", level=2))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="junior")
    )

    assert page.total == 1
    assert page.items[0].name == "Junior Engineer"


async def test_list_paginated_passes_through_filters(service: JobGradeService):
    job_grade = await service.create(JobGradeCreate(code="L1", name="Junior", level=1))
    await service.create(JobGradeCreate(code="L2", name="Senior", level=2))

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), filters=FilterParams(values={"level": 1})
    )

    assert page.total == 1
    assert page.items[0].id == job_grade.id
