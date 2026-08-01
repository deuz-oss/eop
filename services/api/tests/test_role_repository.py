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
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.models.user import User
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository

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
def repo(session: AsyncSession) -> RoleRepository:
    return RoleRepository(session)


@pytest.fixture
async def user(session: AsyncSession) -> User:
    return await UserRepository(session).create(
        email="ada@example.com",
        password_hash=hash_password("correct-horse"),
        full_name="Ada Lovelace",
        is_active=True,
    )


@pytest.fixture
async def other_user(session: AsyncSession) -> User:
    return await UserRepository(session).create(
        email="grace@example.com",
        password_hash=hash_password("correct-horse"),
        full_name="Grace Hopper",
        is_active=True,
    )


async def test_create_and_get(repo: RoleRepository):
    role = await repo.create(name="admin", description="Full access")

    fetched = await repo.get(role.id)

    assert fetched is not None
    assert fetched.name == "admin"
    assert fetched.description == "Full access"


async def test_get_missing_returns_none(repo: RoleRepository):
    assert await repo.get(uuid.uuid4()) is None


async def test_list_returns_created(repo: RoleRepository):
    await repo.create(name="admin")
    await repo.create(name="member")

    items = await repo.list()

    assert {"admin", "member"}.issubset({item.name for item in items})


async def test_update_existing(repo: RoleRepository):
    role = await repo.create(name="before")

    updated = await repo.update(role.id, name="after")

    assert updated is not None
    assert updated.name == "after"


async def test_update_missing_returns_none(repo: RoleRepository):
    assert await repo.update(uuid.uuid4(), name="after") is None


async def test_delete_existing(repo: RoleRepository):
    role = await repo.create(name="admin")

    deleted = await repo.delete(role.id)

    assert deleted is True
    assert await repo.get(role.id) is None


async def test_delete_missing_returns_false(repo: RoleRepository):
    assert await repo.delete(uuid.uuid4()) is False


async def test_exists(repo: RoleRepository):
    role = await repo.create(name="admin")

    assert await repo.exists(role.id) is True
    assert await repo.exists(uuid.uuid4()) is False


async def test_count(repo: RoleRepository):
    await repo.create(name="admin")
    await repo.create(name="member")

    assert await repo.count() == 2


async def test_get_by_name(repo: RoleRepository):
    role = await repo.create(name="admin")

    found = await repo.get_by_name("admin")

    assert found is not None
    assert found.id == role.id
    assert await repo.get_by_name("unknown") is None


async def test_assign_user_and_is_assigned(repo: RoleRepository, user: User):
    role = await repo.create(name="admin")

    assert await repo.is_assigned(role.id, user.id) is False

    await repo.assign_user(role.id, user.id)

    assert await repo.is_assigned(role.id, user.id) is True


async def test_unassign_user(repo: RoleRepository, user: User):
    role = await repo.create(name="admin")
    await repo.assign_user(role.id, user.id)

    removed = await repo.unassign_user(role.id, user.id)

    assert removed is True
    assert await repo.is_assigned(role.id, user.id) is False


async def test_unassign_user_missing_returns_false(repo: RoleRepository, user: User):
    role = await repo.create(name="admin")

    assert await repo.unassign_user(role.id, user.id) is False


async def test_get_role_names_for_user(repo: RoleRepository, user: User, other_user: User):
    admin_role = await repo.create(name="admin")
    member_role = await repo.create(name="member")
    await repo.assign_user(admin_role.id, user.id)
    await repo.assign_user(member_role.id, user.id)
    await repo.assign_user(member_role.id, other_user.id)

    names = await repo.get_role_names_for_user(user.id)

    assert names == {"admin", "member"}
    assert await repo.get_role_names_for_user(other_user.id) == {"member"}
