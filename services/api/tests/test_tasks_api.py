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
    """Ensures the `organizations`/`employees`/`projects`/`tasks` tables
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
def other_org_employee_id(client: TestClient, other_organization_id: str) -> str:
    response = client.post(
        "/employees",
        json={
            "organization_id": other_organization_id,
            "first_name": "Grace",
            "last_name": "Hopper",
            "email": "grace@example.com",
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


def test_create_task_without_assignee(client: TestClient, project_id: str):
    response = client.post(
        "/tasks",
        json={"project_id": project_id, "title": "Write report"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["project_id"] == project_id
    assert body["title"] == "Write report"
    assert body["assignee_id"] is None
    assert body["status"] == "todo"
    uuid.UUID(body["id"])


def test_create_task_with_assignee(client: TestClient, project_id: str, employee_id: str):
    response = client.post(
        "/tasks",
        json={"project_id": project_id, "assignee_id": employee_id, "title": "Review PR"},
    )

    assert response.status_code == 201
    assert response.json()["assignee_id"] == employee_id


def test_create_task_rejects_blank_title(client: TestClient, project_id: str):
    response = client.post("/tasks", json={"project_id": project_id, "title": ""})

    assert response.status_code == 422


def test_create_task_rejects_missing_project(client: TestClient):
    response = client.post("/tasks", json={"project_id": str(uuid.uuid4()), "title": "Orphan"})

    assert response.status_code == 404


def test_create_task_rejects_missing_assignee(client: TestClient, project_id: str):
    response = client.post(
        "/tasks",
        json={"project_id": project_id, "assignee_id": str(uuid.uuid4()), "title": "Ghost"},
    )

    assert response.status_code == 404


def test_create_task_rejects_organization_mismatch(
    client: TestClient, project_id: str, other_org_employee_id: str
):
    response = client.post(
        "/tasks",
        json={
            "project_id": project_id,
            "assignee_id": other_org_employee_id,
            "title": "Mismatch",
        },
    )

    assert response.status_code == 409


def test_get_task(client: TestClient, project_id: str):
    created = client.post("/tasks", json={"project_id": project_id, "title": "Write report"}).json()

    response = client.get(f"/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json()["title"] == "Write report"


def test_get_task_not_found(client: TestClient):
    response = client.get(f"/tasks/{uuid.uuid4()}")

    assert response.status_code == 404


def test_list_tasks(client: TestClient, project_id: str):
    client.post("/tasks", json={"project_id": project_id, "title": "Task A"})
    client.post("/tasks", json={"project_id": project_id, "title": "Task B"})

    response = client.get("/tasks")

    assert response.status_code == 200
    titles = {task["title"] for task in response.json()}
    assert {"Task A", "Task B"}.issubset(titles)


def test_update_task(client: TestClient, project_id: str):
    created = client.post("/tasks", json={"project_id": project_id, "title": "Before"}).json()

    response = client.patch(f"/tasks/{created['id']}", json={"title": "After"})

    assert response.status_code == 200
    assert response.json()["title"] == "After"


def test_update_task_not_found(client: TestClient):
    response = client.patch(f"/tasks/{uuid.uuid4()}", json={"title": "After"})

    assert response.status_code == 404


def test_update_task_assigns_employee(client: TestClient, project_id: str, employee_id: str):
    created = client.post("/tasks", json={"project_id": project_id, "title": "Task"}).json()

    response = client.patch(f"/tasks/{created['id']}", json={"assignee_id": employee_id})

    assert response.status_code == 200
    assert response.json()["assignee_id"] == employee_id


def test_update_task_removes_assignee(client: TestClient, project_id: str, employee_id: str):
    created = client.post(
        "/tasks", json={"project_id": project_id, "assignee_id": employee_id, "title": "Task"}
    ).json()

    response = client.patch(f"/tasks/{created['id']}", json={"assignee_id": None})

    assert response.status_code == 200
    assert response.json()["assignee_id"] is None


def test_update_task_rejects_missing_assignee(client: TestClient, project_id: str):
    created = client.post("/tasks", json={"project_id": project_id, "title": "Task"}).json()

    response = client.patch(f"/tasks/{created['id']}", json={"assignee_id": str(uuid.uuid4())})

    assert response.status_code == 404


def test_update_task_rejects_organization_mismatch(
    client: TestClient, project_id: str, other_org_employee_id: str
):
    created = client.post("/tasks", json={"project_id": project_id, "title": "Task"}).json()

    response = client.patch(f"/tasks/{created['id']}", json={"assignee_id": other_org_employee_id})

    assert response.status_code == 409


def test_delete_task(client: TestClient, project_id: str):
    created = client.post("/tasks", json={"project_id": project_id, "title": "To delete"}).json()

    response = client.delete(f"/tasks/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/tasks/{created['id']}").status_code == 404


def test_delete_task_not_found(client: TestClient):
    response = client.delete(f"/tasks/{uuid.uuid4()}")

    assert response.status_code == 404
