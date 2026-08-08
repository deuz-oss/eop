import asyncio
import uuid
from collections.abc import Generator

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
            await conn.execute(text("TRUNCATE TABLE payroll_runs, users CASCADE"))
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


def _create_payroll_run(
    client: TestClient,
    headers: dict[str, str],
    *,
    code: str = "RUN-001",
    name: str = "First Run",
) -> dict:
    response = client.post(
        "/hr/payroll-runs",
        json={"code": code, "name": name},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_payroll_run_requires_authentication(client: TestClient):
    response = client.post("/hr/payroll-runs", json={"code": "RUN-001", "name": "First Run"})

    assert response.status_code == 401


def test_list_payroll_runs_requires_authentication(client: TestClient):
    response = client.get("/hr/payroll-runs")

    assert response.status_code == 401


def test_get_payroll_run_requires_authentication(client: TestClient):
    response = client.get(f"/hr/payroll-runs/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_payroll_run_requires_authentication(client: TestClient):
    response = client.put(f"/hr/payroll-runs/{uuid.uuid4()}", json={"name": "New Name"})

    assert response.status_code == 401


def test_delete_payroll_run_requires_authentication(client: TestClient):
    response = client.delete(f"/hr/payroll-runs/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_payroll_run(client: TestClient, user_headers: dict[str, str]):
    body = _create_payroll_run(client, user_headers)

    assert body["code"] == "RUN-001"
    assert body["name"] == "First Run"
    uuid.UUID(body["id"])


def test_create_payroll_run_rejects_blank_name(client: TestClient, user_headers: dict[str, str]):
    response = client.post(
        "/hr/payroll-runs", json={"code": "RUN-001", "name": ""}, headers=user_headers
    )

    assert response.status_code == 422


def test_create_payroll_run_rejects_duplicate_code(
    client: TestClient, user_headers: dict[str, str]
):
    _create_payroll_run(client, user_headers, code="RUN-001")

    response = client.post(
        "/hr/payroll-runs",
        json={"code": "RUN-001", "name": "Other"},
        headers=user_headers,
    )

    assert response.status_code == 409


def test_get_payroll_run(client: TestClient, user_headers: dict[str, str]):
    created = _create_payroll_run(client, user_headers, code="RUN-001", name="First Run")

    response = client.get(f"/hr/payroll-runs/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "First Run"


def test_get_payroll_run_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/payroll-runs/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_payroll_runs(client: TestClient, user_headers: dict[str, str]):
    _create_payroll_run(client, user_headers, code="RUN-001", name="First Run")
    _create_payroll_run(client, user_headers, code="RUN-002", name="Second Run")

    response = client.get("/hr/payroll-runs", headers=user_headers)

    assert response.status_code == 200
    names = {item["name"] for item in response.json()}
    assert {"First Run", "Second Run"}.issubset(names)


def test_list_payroll_runs_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    for i in range(3):
        _create_payroll_run(client, user_headers, code=f"RUN-{i}", name=f"Run {i}")

    response = client.get("/hr/payroll-runs/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_payroll_runs_paginated_custom_offset(
    client: TestClient, user_headers: dict[str, str]
):
    for i in range(5):
        _create_payroll_run(client, user_headers, code=f"RUN-{i}", name=f"Run {i}")

    response = client.get(
        "/hr/payroll-runs/paginated", headers=user_headers, params={"offset": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_payroll_runs_paginated_search_by_name(
    client: TestClient, user_headers: dict[str, str]
):
    _create_payroll_run(client, user_headers, code="RUN-001", name="August Run")
    _create_payroll_run(client, user_headers, code="RUN-002", name="September Run")

    response = client.get(
        "/hr/payroll-runs/paginated", headers=user_headers, params={"q": "august"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "August Run"


def test_list_payroll_runs_paginated_search_by_code(
    client: TestClient, user_headers: dict[str, str]
):
    _create_payroll_run(client, user_headers, code="RUN-AUG-01", name="First")
    _create_payroll_run(client, user_headers, code="RUN-SEP-01", name="Second")

    response = client.get(
        "/hr/payroll-runs/paginated", headers=user_headers, params={"q": "aug"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "RUN-AUG-01"


def test_list_payroll_runs_paginated_no_query_returns_all(
    client: TestClient, user_headers: dict[str, str]
):
    _create_payroll_run(client, user_headers, code="RUN-001", name="First Run")
    _create_payroll_run(client, user_headers, code="RUN-002", name="Second Run")

    response = client.get("/hr/payroll-runs/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_update_payroll_run(client: TestClient, user_headers: dict[str, str]):
    created = _create_payroll_run(client, user_headers, name="Before")

    response = client.put(
        f"/hr/payroll-runs/{created['id']}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_payroll_run_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/hr/payroll-runs/{uuid.uuid4()}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 404


def test_update_payroll_run_rejects_duplicate_code(
    client: TestClient, user_headers: dict[str, str]
):
    _create_payroll_run(client, user_headers, code="RUN-001")
    other = _create_payroll_run(client, user_headers, code="RUN-002")

    response = client.put(
        f"/hr/payroll-runs/{other['id']}", json={"code": "RUN-001"}, headers=user_headers
    )

    assert response.status_code == 409


def test_delete_payroll_run(client: TestClient, user_headers: dict[str, str]):
    created = _create_payroll_run(client, user_headers, name="To Delete")

    response = client.delete(f"/hr/payroll-runs/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/hr/payroll-runs/{created['id']}", headers=user_headers).status_code == 404
    )


def test_delete_payroll_run_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/hr/payroll-runs/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404
