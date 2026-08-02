import asyncio
import uuid
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
from eop_api.middleware.request_id import REQUEST_ID_HEADER
from eop_api.models.user import User
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository

PROBLEM_DETAILS_FIELDS = {"type", "title", "status", "detail", "instance", "request_id"}


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures the tables exercised by these tests exist and are empty.

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
            await conn.execute(text("TRUNCATE TABLE users, roles, organizations CASCADE"))
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_truncate())


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
            full_name="Test User",
            is_active=True,
        )
        await session.commit()
        session.expunge(user)
    await engine.dispose()
    return user


async def _grant_role(*, user_id: uuid.UUID, role_name: str) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = RoleRepository(session)
        role = await repo.get_by_name(role_name)
        if role is None:
            role = await repo.create(name=role_name)
        await repo.assign_user(role.id, user_id)
        await session.commit()
    await engine.dispose()


@pytest.fixture
def member_user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def member_token(member_user: User) -> str:
    return create_access_token(subject=str(member_user.id))


def test_not_found_returns_problem_details(client: TestClient):
    missing_id = uuid.uuid4()

    response = client.get(f"/organizations/{missing_id}")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert PROBLEM_DETAILS_FIELDS.issubset(body.keys())
    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["detail"] == "Organization not found"
    assert body["instance"] == f"/organizations/{missing_id}"


def test_unauthorized_returns_problem_details(client: TestClient):
    response = client.get("/auth/me")

    assert response.status_code == 401
    body = response.json()
    assert PROBLEM_DETAILS_FIELDS.issubset(body.keys())
    assert body["status"] == 401
    assert body["title"] == "Unauthorized"
    assert body["instance"] == "/auth/me"


def test_forbidden_returns_problem_details(client: TestClient, member_token: str):
    response = client.post(
        "/roles",
        json={"name": "new-role"},
        headers={"Authorization": f"Bearer {member_token}"},
    )

    assert response.status_code == 403
    body = response.json()
    assert PROBLEM_DETAILS_FIELDS.issubset(body.keys())
    assert body["status"] == 403
    assert body["title"] == "Forbidden"
    assert body["instance"] == "/roles"


def test_validation_error_returns_problem_details(client: TestClient):
    response = client.post("/organizations", json={"name": ""})

    assert response.status_code == 422
    body = response.json()
    assert PROBLEM_DETAILS_FIELDS.issubset(body.keys())
    assert body["status"] == 422
    assert "errors" in body
    assert isinstance(body["errors"], list) and body["errors"]
    error = body["errors"][0]
    assert {"loc", "msg", "type"}.issubset(error.keys())
    assert "name" in error["loc"]


def test_request_id_included_and_matches_response_header(client: TestClient):
    response = client.get(f"/organizations/{uuid.uuid4()}")

    body = response.json()
    assert body["request_id"]
    assert body["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_instance_reflects_request_path(client: TestClient):
    organization_id = uuid.uuid4()

    response = client.patch(f"/organizations/{organization_id}", json={"name": "After"})

    assert response.status_code == 404
    assert response.json()["instance"] == f"/organizations/{organization_id}"
