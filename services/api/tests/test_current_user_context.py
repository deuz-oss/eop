import asyncio
from collections.abc import Generator

import pytest
from conftest import clean_database
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.request_context import current_user_id
from eop_api.core.security import hash_password
from eop_api.dependencies.auth import CurrentUser
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository

whoami_router = APIRouter()


@whoami_router.get("/__whoami")
async def whoami(_: CurrentUser) -> dict:
    return {"user_id": current_user_id()}


@whoami_router.get("/__whoami-anonymous")
async def whoami_anonymous() -> dict:
    return {"user_id": current_user_id()}


app.include_router(whoami_router)


_tables = pytest.fixture(autouse=True)(clean_database)


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


async def _create_user(*, email: str, password: str) -> User:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        user = await UserRepository(session).create(
            email=email,
            password_hash=hash_password(password),
            full_name="Ada Lovelace",
            is_active=True,
        )
        await session.commit()
        session.expunge(user)
    await engine.dispose()
    return user


@pytest.fixture
def active_user() -> User:
    return asyncio.run(_create_user(email="ada@example.com", password="correct-horse"))


def _login(client: TestClient) -> str:
    response = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "correct-horse"}
    )
    token: str = response.json()["access_token"]
    return token


def test_authenticated_request_exposes_current_user_id(client: TestClient, active_user: User):
    token = _login(client)

    response = client.get("/__whoami", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user_id"] == str(active_user.id)


def test_anonymous_request_current_user_id_is_none(client: TestClient):
    response = client.get("/__whoami-anonymous")

    assert response.status_code == 200
    assert response.json()["user_id"] is None


def test_user_id_contextvar_is_reset_after_request_completes(client: TestClient, active_user: User):
    token = _login(client)

    client.get("/__whoami", headers={"Authorization": f"Bearer {token}"})

    assert current_user_id() is None


def test_user_id_contextvar_does_not_leak_into_next_anonymous_request(
    client: TestClient, active_user: User
):
    token = _login(client)

    authenticated_response = client.get("/__whoami", headers={"Authorization": f"Bearer {token}"})
    anonymous_response = client.get("/__whoami-anonymous")

    assert authenticated_response.json()["user_id"] == str(active_user.id)
    assert anonymous_response.json()["user_id"] is None
