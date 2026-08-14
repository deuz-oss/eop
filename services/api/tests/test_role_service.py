import uuid
from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository
from eop_api.schemas.role import RoleCreate, RoleUpdate
from eop_api.services.role import (
    DuplicateRoleAssignmentError,
    DuplicateRoleNameError,
    RoleNotFoundError,
    RoleService,
    UserNotFoundError,
)
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def session_factory() -> AsyncGenerator[Callable[[], AsyncSession]]:
    """A session factory backed by the real (migration-managed) tables.

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
            await conn.execute(text("TRUNCATE TABLE users, roles CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> RoleService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return RoleService(uow_factory)


@pytest.fixture
async def user(session_factory: Callable[[], AsyncSession]) -> User:
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email="ada@example.com",
            password_hash=hash_password("correct-horse"),
            full_name="Ada Lovelace",
            is_active=True,
        )
        await session.commit()
        session.expunge(user)
        return user


async def test_create_and_get(service: RoleService):
    role = await service.create(RoleCreate(name="admin", description="Full access"))

    fetched = await service.get(role.id)

    assert fetched is not None
    assert fetched.name == "admin"
    assert fetched.description == "Full access"


async def test_create_rejects_duplicate_name(service: RoleService):
    await service.create(RoleCreate(name="admin"))

    with pytest.raises(DuplicateRoleNameError):
        await service.create(RoleCreate(name="admin"))


async def test_get_missing_returns_none(service: RoleService):
    assert await service.get(uuid.uuid4()) is None


async def test_list_returns_created(service: RoleService):
    await service.create(RoleCreate(name="admin"))
    await service.create(RoleCreate(name="member"))

    items = await service.list()

    assert {"admin", "member"}.issubset({item.name for item in items})


async def test_update_existing(service: RoleService):
    role = await service.create(RoleCreate(name="before"))

    updated = await service.update(role.id, RoleUpdate(name="after"))

    assert updated is not None
    assert updated.name == "after"


async def test_update_missing_returns_none(service: RoleService):
    assert await service.update(uuid.uuid4(), RoleUpdate(name="after")) is None


async def test_update_rejects_duplicate_name(service: RoleService):
    await service.create(RoleCreate(name="admin"))
    other = await service.create(RoleCreate(name="member"))

    with pytest.raises(DuplicateRoleNameError):
        await service.update(other.id, RoleUpdate(name="admin"))


async def test_update_allows_unchanged_name(service: RoleService):
    role = await service.create(RoleCreate(name="admin", description="Before"))

    updated = await service.update(role.id, RoleUpdate(name="admin", description="After"))

    assert updated is not None
    assert updated.description == "After"


async def test_delete_existing(service: RoleService):
    role = await service.create(RoleCreate(name="admin"))

    deleted = await service.delete(role.id)

    assert deleted is True
    assert await service.get(role.id) is None


async def test_delete_missing_returns_false(service: RoleService):
    assert await service.delete(uuid.uuid4()) is False


async def test_assign_role(service: RoleService, user: User):
    role = await service.create(RoleCreate(name="admin"))

    await service.assign_role(role.id, user.id)

    assert await service.user_has_role(user.id, "admin") is True


async def test_assign_role_rejects_missing_role(service: RoleService, user: User):
    with pytest.raises(RoleNotFoundError):
        await service.assign_role(uuid.uuid4(), user.id)


async def test_assign_role_rejects_missing_user(service: RoleService):
    role = await service.create(RoleCreate(name="admin"))

    with pytest.raises(UserNotFoundError):
        await service.assign_role(role.id, uuid.uuid4())


async def test_assign_role_rejects_duplicate(service: RoleService, user: User):
    role = await service.create(RoleCreate(name="admin"))
    await service.assign_role(role.id, user.id)

    with pytest.raises(DuplicateRoleAssignmentError):
        await service.assign_role(role.id, user.id)


async def test_remove_role(service: RoleService, user: User):
    role = await service.create(RoleCreate(name="admin"))
    await service.assign_role(role.id, user.id)

    removed = await service.remove_role(role.id, user.id)

    assert removed is True
    assert await service.user_has_role(user.id, "admin") is False


async def test_remove_role_not_assigned_returns_false(service: RoleService, user: User):
    role = await service.create(RoleCreate(name="admin"))

    assert await service.remove_role(role.id, user.id) is False


async def test_remove_role_rejects_missing_role(service: RoleService, user: User):
    with pytest.raises(RoleNotFoundError):
        await service.remove_role(uuid.uuid4(), user.id)


async def test_remove_role_rejects_missing_user(service: RoleService):
    role = await service.create(RoleCreate(name="admin"))

    with pytest.raises(UserNotFoundError):
        await service.remove_role(role.id, uuid.uuid4())


async def test_user_has_role_false_when_unassigned(service: RoleService, user: User):
    await service.create(RoleCreate(name="admin"))

    assert await service.user_has_role(user.id, "admin") is False
