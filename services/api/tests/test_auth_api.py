import asyncio
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import create_access_token, hash_password
from eop_api.db.base import Base
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures the `users` table exists and is empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables.
    """

    async def _create() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _truncate() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE users CASCADE"))
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_truncate())


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


async def _create_user(*, email: str, password: str, is_active: bool = True) -> User:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email=email,
            password_hash=hash_password(password),
            full_name="Ada Lovelace",
            is_active=is_active,
        )
        await session.commit()
        session.expunge(user)
    await engine.dispose()
    return user


@pytest.fixture
def active_user() -> User:
    return asyncio.run(_create_user(email="ada@example.com", password="correct-horse"))


@pytest.fixture
def inactive_user() -> User:
    return asyncio.run(
        _create_user(email="inactive@example.com", password="correct-horse", is_active=False)
    )


def test_login_succeeds_with_correct_credentials(client: TestClient, active_user: User):
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


def test_login_rejects_wrong_password(client: TestClient, active_user: User):
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "wrong-password"}
    )

    assert response.status_code == 401


def test_login_rejects_unknown_email(client: TestClient):
    response = client.post(
        "/auth/login", json={"email": "unknown@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 401


def test_login_rejects_inactive_user(client: TestClient, inactive_user: User):
    response = client.post(
        "/auth/login", json={"email": "inactive@example.com", "password": "correct-horse"}
    )

    assert response.status_code == 401


def test_me_returns_current_user(client: TestClient, active_user: User):
    login_response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )
    token = login_response.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert body["id"] == str(active_user.id)


def test_me_rejects_missing_token(client: TestClient):
    response = client.get("/auth/me")

    assert response.status_code in (401, 403)


def test_me_rejects_invalid_token(client: TestClient):
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-valid-token"})

    assert response.status_code == 401


def test_me_rejects_token_for_inactive_user(client: TestClient, inactive_user: User):
    token = create_access_token(subject=str(inactive_user.id))

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
