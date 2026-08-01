import asyncio
from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures all tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables. Truncating `organizations`/`users` with CASCADE also clears
    everything that references them transitively.
    """

    async def _create() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _truncate() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE organizations, users CASCADE"))
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


@pytest.fixture
def user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def user_headers(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def organization_id(client: TestClient, user_headers: dict[str, str]) -> str:
    response = client.post("/organizations", json={"name": "Acme Corp"})
    return response.json()["id"]


@pytest.fixture
def employee_id(client: TestClient, organization_id: str) -> str:
    response = client.post(
        "/employees",
        json={
            "organization_id": organization_id,
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        },
    )
    return response.json()["id"]


@pytest.fixture
def project_id(client: TestClient, organization_id: str) -> str:
    response = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Apollo", "code": "APO"},
    )
    return response.json()["id"]


def test_get_dashboard_requires_authentication(client: TestClient):
    response = client.get("/dashboard")

    assert response.status_code == 401


def test_get_dashboard_returns_200_for_authenticated_user(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/dashboard", headers=user_headers)

    assert response.status_code == 200


def test_get_dashboard_values_match_seeded_database(
    client: TestClient,
    user_headers: dict[str, str],
    organization_id: str,
    employee_id: str,
    project_id: str,
):
    client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Engineer",
            "start_date": str(date(2026, 1, 1)),
        },
    )
    client.post("/tasks", json={"project_id": project_id, "title": "A", "status": "todo"})
    client.post("/tasks", json={"project_id": project_id, "title": "B", "status": "todo"})
    client.post("/tasks", json={"project_id": project_id, "title": "C", "status": "done"})

    response = client.get("/dashboard", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["organizations"] == 1
    assert body["projects"] == 1
    assert body["employees"] == 1
    assert body["assignments"] == 1
    assert body["tasks"] == 3
    assert body["tasks_by_status"] == {"todo": 2, "done": 1}
