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
    """Ensures the `organizations`/`employees`/`projects`/`assignments` tables
    exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables. Truncating `organizations` with CASCADE also clears everything that
    references it transitively.
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
    response = client.post("/organizations", json={"name": "Acme Corp"}, headers=user_headers)
    return response.json()["id"]


@pytest.fixture
def other_organization_id(client: TestClient, user_headers: dict[str, str]) -> str:
    response = client.post("/organizations", json={"name": "Globex Corp"}, headers=user_headers)
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


@pytest.fixture
def other_org_project_id(client: TestClient, other_organization_id: str) -> str:
    response = client.post(
        "/projects",
        json={"organization_id": other_organization_id, "name": "Zeus", "code": "ZEU"},
    )
    return response.json()["id"]


def test_create_assignment(client: TestClient, employee_id: str, project_id: str):
    response = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["employee_id"] == employee_id
    assert body["project_id"] == project_id
    assert body["role"] == "Engineer"
    assert body["start_date"] == "2026-01-01"
    assert body["end_date"] is None
    uuid.UUID(body["id"])


def test_create_assignment_rejects_blank_role(
    client: TestClient, employee_id: str, project_id: str
):
    response = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "",
            "start_date": "2026-01-01",
        },
    )

    assert response.status_code == 422


def test_create_assignment_rejects_missing_employee(client: TestClient, project_id: str):
    response = client.post(
        "/assignments",
        json={
            "employee_id": str(uuid.uuid4()),
            "project_id": project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    )

    assert response.status_code == 404


def test_create_assignment_rejects_missing_project(client: TestClient, employee_id: str):
    response = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": str(uuid.uuid4()),
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    )

    assert response.status_code == 404


def test_create_assignment_rejects_organization_mismatch(
    client: TestClient, employee_id: str, other_org_project_id: str
):
    response = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": other_org_project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    )

    assert response.status_code == 409


def test_create_assignment_rejects_duplicate(client: TestClient, employee_id: str, project_id: str):
    client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    )

    response = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Lead",
            "start_date": "2026-01-01",
        },
    )

    assert response.status_code == 409


def test_get_assignment(client: TestClient, employee_id: str, project_id: str):
    created = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    ).json()

    response = client.get(f"/assignments/{created['id']}")

    assert response.status_code == 200
    assert response.json()["role"] == "Engineer"


def test_get_assignment_not_found(client: TestClient):
    response = client.get(f"/assignments/{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_assignments(
    client: TestClient, organization_id: str, employee_id: str, project_id: str
):
    other_project_id = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Zeus", "code": "ZEU"},
    ).json()["id"]

    client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    )
    client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": other_project_id,
            "role": "Lead",
            "start_date": "2026-01-01",
        },
    )

    response = client.get("/assignments")

    assert response.status_code == 200
    roles = {assignment["role"] for assignment in response.json()}
    assert {"Engineer", "Lead"}.issubset(roles)


def test_update_assignment(client: TestClient, employee_id: str, project_id: str):
    created = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Before",
            "start_date": "2026-01-01",
        },
    ).json()

    response = client.patch(f"/assignments/{created['id']}", json={"role": "After"})

    assert response.status_code == 200
    assert response.json()["role"] == "After"


def test_update_assignment_not_found(client: TestClient):
    response = client.patch(f"/assignments/{uuid.uuid4()}", json={"role": "After"})

    assert response.status_code == 404


def test_update_assignment_rejects_organization_mismatch(
    client: TestClient, employee_id: str, project_id: str, other_org_project_id: str
):
    created = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    ).json()

    response = client.patch(
        f"/assignments/{created['id']}", json={"project_id": other_org_project_id}
    )

    assert response.status_code == 409


def test_update_assignment_rejects_duplicate(
    client: TestClient, organization_id: str, employee_id: str, project_id: str
):
    other_project_id = client.post(
        "/projects",
        json={"organization_id": organization_id, "name": "Zeus", "code": "ZEU"},
    ).json()["id"]

    client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    )
    other = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": other_project_id,
            "role": "Lead",
            "start_date": "2026-01-01",
        },
    ).json()

    response = client.patch(f"/assignments/{other['id']}", json={"project_id": project_id})

    assert response.status_code == 409


def test_delete_assignment(client: TestClient, employee_id: str, project_id: str):
    created = client.post(
        "/assignments",
        json={
            "employee_id": employee_id,
            "project_id": project_id,
            "role": "Engineer",
            "start_date": "2026-01-01",
        },
    ).json()

    response = client.delete(f"/assignments/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/assignments/{created['id']}").status_code == 404


def test_delete_assignment_not_found(client: TestClient):
    response = client.delete(f"/assignments/{uuid.uuid4()}")

    assert response.status_code == 404
