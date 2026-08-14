from collections.abc import AsyncGenerator, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import create_access_token, decode_access_token, hash_password
from eop_api.db.base import Base
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository
from eop_api.services.auth import (
    AuthService,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
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
            await conn.execute(text("TRUNCATE TABLE users CASCADE"))
        await engine.dispose()


@pytest.fixture
def service(session_factory: Callable[[], AsyncSession]) -> AuthService:
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(  # noqa: E731
        session_factory
    )
    return AuthService(uow_factory)


@pytest.fixture
async def active_user(session_factory: Callable[[], AsyncSession]) -> User:
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


@pytest.fixture
async def inactive_user(session_factory: Callable[[], AsyncSession]) -> User:
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email="inactive@example.com",
            password_hash=hash_password("correct-horse"),
            full_name="Inactive User",
            is_active=False,
        )
        await session.commit()
        session.expunge(user)
        return user


async def test_authenticate_success(service: AuthService, active_user: User):
    user = await service.authenticate("ada@example.com", "correct-horse")

    assert user.id == active_user.id
    assert user.email == "ada@example.com"


async def test_authenticate_rejects_wrong_password(service: AuthService, active_user: User):
    with pytest.raises(InvalidCredentialsError):
        await service.authenticate("ada@example.com", "wrong-password")


async def test_authenticate_rejects_unknown_email(service: AuthService):
    with pytest.raises(InvalidCredentialsError):
        await service.authenticate("unknown@example.com", "correct-horse")


async def test_authenticate_rejects_inactive_user(service: AuthService, inactive_user: User):
    with pytest.raises(InactiveUserError):
        await service.authenticate("inactive@example.com", "correct-horse")


async def test_login_returns_a_valid_token(service: AuthService, active_user: User):
    token = await service.login("ada@example.com", "correct-horse")

    payload = decode_access_token(token)
    assert payload["sub"] == str(active_user.id)


async def test_login_rejects_wrong_password(service: AuthService, active_user: User):
    with pytest.raises(InvalidCredentialsError):
        await service.login("ada@example.com", "wrong-password")


async def test_get_current_user_returns_user_for_valid_token(
    service: AuthService, active_user: User
):
    token = await service.login("ada@example.com", "correct-horse")

    user = await service.get_current_user(token)

    assert user.id == active_user.id


async def test_get_current_user_rejects_invalid_token(service: AuthService):
    with pytest.raises(InvalidTokenError):
        await service.get_current_user("not-a-valid-token")


async def test_get_current_user_rejects_inactive_user(service: AuthService, inactive_user: User):
    token = create_access_token(subject=str(inactive_user.id))

    with pytest.raises(InvalidTokenError):
        await service.get_current_user(token)
