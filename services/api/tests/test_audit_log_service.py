import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.audit import AuditAction, AuditEntityType
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository
from eop_api.schemas.pagination import PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.services.audit_log import AuditLogService
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def service() -> AsyncGenerator[AuditLogService]:
    """A service backed by the real (migration-managed) `audit_logs` table.

    Unlike the repository tests, the service commits internally (it owns the
    transaction boundary), so rows are truncated after each test instead of
    relying on a rolled-back transaction.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731

    try:
        yield AuditLogService(uow_factory)
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE audit_logs, users CASCADE"))
        await engine.dispose()


async def _create_user() -> User:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email="auditor@example.com",
            password_hash=hash_password("auditor-pass"),
            full_name="Auditor",
            is_active=True,
        )
        await session.commit()
        session.expunge(user)
    await engine.dispose()
    return user


async def test_record_creates_entry(service: AuditLogService):
    entity_id = uuid.uuid4()
    user = await _create_user()

    audit_log = await service.record(
        user_id=user.id,
        action=AuditAction.CREATE,
        entity_type=AuditEntityType.ORGANIZATION,
        entity_id=entity_id,
        details={"name": "Acme Corp"},
    )

    assert audit_log.id is not None
    assert audit_log.user_id == user.id
    assert audit_log.action == AuditAction.CREATE
    assert audit_log.entity_type == AuditEntityType.ORGANIZATION
    assert audit_log.entity_id == entity_id
    assert audit_log.details == {"name": "Acme Corp"}


async def test_record_persists_action_and_entity_type_as_plain_strings(service: AuditLogService):
    """The service accepts enums, but the DB column stays a plain string."""
    audit_log = await service.record(
        user_id=None,
        action=AuditAction.UPDATE,
        entity_type=AuditEntityType.ROLE,
        entity_id=uuid.uuid4(),
    )

    assert audit_log.action == "update"
    assert audit_log.entity_type == "role"


async def test_record_without_user_or_details(service: AuditLogService):
    audit_log = await service.record(
        user_id=None,
        action=AuditAction.DELETE,
        entity_type=AuditEntityType.PROJECT,
        entity_id=uuid.uuid4(),
    )

    assert audit_log.user_id is None
    assert audit_log.details is None


async def test_record_commits_and_is_visible_from_a_new_session(service: AuditLogService):
    audit_log = await service.record(
        user_id=None,
        action=AuditAction.CREATE,
        entity_type=AuditEntityType.ORGANIZATION,
        entity_id=uuid.uuid4(),
    )

    page = await service.list_paginated(PaginationParams(offset=0, limit=50))

    assert any(item.id == audit_log.id for item in page.items)


async def test_list_paginated_passes_through_offset_and_limit(service: AuditLogService):
    for _i in range(5):
        await service.record(
            user_id=None,
            action=AuditAction.CREATE,
            entity_type=AuditEntityType.ORGANIZATION,
            entity_id=uuid.uuid4(),
        )

    page = await service.list_paginated(PaginationParams(offset=1, limit=2))

    assert page.total == 5
    assert page.offset == 1
    assert page.limit == 2
    assert len(page.items) == 2


async def test_list_paginated_passes_through_search(service: AuditLogService):
    await service.record(
        user_id=None,
        action=AuditAction.CREATE,
        entity_type=AuditEntityType.ORGANIZATION,
        entity_id=uuid.uuid4(),
    )
    await service.record(
        user_id=None,
        action=AuditAction.CREATE,
        entity_type=AuditEntityType.PROJECT,
        entity_id=uuid.uuid4(),
    )

    page = await service.list_paginated(
        PaginationParams(offset=0, limit=50), SearchParams(q="organization")
    )

    assert page.total == 1
    assert page.items[0].entity_type == "organization"


async def test_list_paginated_without_search_returns_all(service: AuditLogService):
    await service.record(
        user_id=None,
        action=AuditAction.CREATE,
        entity_type=AuditEntityType.ORGANIZATION,
        entity_id=uuid.uuid4(),
    )
    await service.record(
        user_id=None,
        action=AuditAction.CREATE,
        entity_type=AuditEntityType.PROJECT,
        entity_id=uuid.uuid4(),
    )

    page = await service.list_paginated(PaginationParams(offset=0, limit=50))

    assert page.total == 2
