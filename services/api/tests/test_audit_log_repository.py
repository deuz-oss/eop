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
from eop_api.core.audit import AuditAction, AuditEntityType
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.repositories.audit_log import AuditLogRepository
from eop_api.schemas.search import SearchParams

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
    """A single connection with its own transaction, rolled back after the test.

    The tables are real, migration-managed tables shared with the running
    application, so tests must never commit or drop them. Everything a test does
    happens inside one uncommitted transaction that is discarded on teardown.
    """
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
def repo(session: AsyncSession) -> AuditLogRepository:
    return AuditLogRepository(session)


async def test_create_and_get(repo: AuditLogRepository):
    entity_id = uuid.uuid4()
    audit_log = await repo.create(
        user_id=None,
        action=AuditAction.CREATE.value,
        entity_type=AuditEntityType.ORGANIZATION.value,
        entity_id=entity_id,
        details={"name": "Acme Corp"},
    )

    fetched = await repo.get(audit_log.id)

    assert fetched is not None
    assert fetched.action == "create"
    assert fetched.entity_type == "organization"
    assert fetched.entity_id == entity_id
    assert fetched.details == {"name": "Acme Corp"}
    assert fetched.user_id is None


async def test_get_missing_returns_none(repo: AuditLogRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_paginate_returns_total_and_page_slice(repo: AuditLogRepository):
    for _i in range(5):
        await repo.create(
            user_id=None,
            action=AuditAction.CREATE.value,
            entity_type=AuditEntityType.ORGANIZATION.value,
            entity_id=uuid.uuid4(),
        )

    page = await repo.paginate(offset=1, limit=2)

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_paginate_defaults(repo: AuditLogRepository):
    for _i in range(3):
        await repo.create(
            user_id=None,
            action=AuditAction.CREATE.value,
            entity_type=AuditEntityType.ORGANIZATION.value,
            entity_id=uuid.uuid4(),
        )

    page = await repo.paginate()

    assert page.offset == 0
    assert page.limit == 50
    assert page.total == 3
    assert len(page.items) == 3


async def test_paginate_search_matches_entity_type(repo: AuditLogRepository):
    await repo.create(
        user_id=None,
        action=AuditAction.CREATE.value,
        entity_type=AuditEntityType.ORGANIZATION.value,
        entity_id=uuid.uuid4(),
    )
    await repo.create(
        user_id=None,
        action=AuditAction.CREATE.value,
        entity_type=AuditEntityType.PROJECT.value,
        entity_id=uuid.uuid4(),
    )

    page = await repo.paginate(search=SearchParams(q="organization"))

    assert page.total == 1
    assert page.items[0].entity_type == "organization"


async def test_paginate_search_matches_action(repo: AuditLogRepository):
    await repo.create(
        user_id=None,
        action=AuditAction.CREATE.value,
        entity_type=AuditEntityType.ORGANIZATION.value,
        entity_id=uuid.uuid4(),
    )
    await repo.create(
        user_id=None,
        action=AuditAction.DELETE.value,
        entity_type=AuditEntityType.ORGANIZATION.value,
        entity_id=uuid.uuid4(),
    )

    page = await repo.paginate(search=SearchParams(q="delete"))

    assert page.total == 1
    assert page.items[0].action == "delete"


async def test_paginate_no_search_returns_all_rows(repo: AuditLogRepository):
    await repo.create(
        user_id=None,
        action=AuditAction.CREATE.value,
        entity_type=AuditEntityType.ORGANIZATION.value,
        entity_id=uuid.uuid4(),
    )
    await repo.create(
        user_id=None,
        action=AuditAction.CREATE.value,
        entity_type=AuditEntityType.PROJECT.value,
        entity_id=uuid.uuid4(),
    )

    page = await repo.paginate(search=None)

    assert page.total == 2
