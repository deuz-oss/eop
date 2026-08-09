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
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository

# Recruitment Authorization: Role Based (`RequireRole("admin")`), mirroring
# `test_payroll_runs_api.py`'s exact fixture/test pattern -- reused
# unmodified from Recruitment Authorization (Iteration 1 addendum).


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    async def _create() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _truncate() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE organizations, candidates, users CASCADE"))
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
def admin_user() -> User:
    return asyncio.run(_create_user(email="admin@example.com", password="admin-pass"))


async def _seed_admin(user_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = RoleRepository(session)
        role = await repo.get_by_name("admin")
        if role is None:
            role = await repo.create(name="admin")
        await repo.assign_user(role.id, user_id)
        await session.commit()
    await engine.dispose()


@pytest.fixture
def admin_headers(client: TestClient, admin_user: User) -> dict[str, str]:
    asyncio.run(_seed_admin(admin_user.id))

    response = client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "admin-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def member_user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def member_headers(client: TestClient, member_user: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_application(client: TestClient, headers: dict[str, str]) -> str:
    suffix = uuid.uuid4().hex[:8]
    candidate = client.post(
        "/recruitment/candidates",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "email": f"ada-{suffix}@example.com",
        },
        headers=headers,
    ).json()
    organization = client.post("/organizations", json={"name": f"Acme {suffix}"}).json()
    department = client.post(
        "/departments",
        json={
            "name": "Engineering",
            "code": f"ENG-{suffix}",
            "organization_id": organization["id"],
        },
        headers=headers,
    ).json()
    position = client.post(
        "/positions",
        json={
            "name": "Engineer",
            "code": f"POS-{suffix}",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=headers,
    ).json()
    job_requisition = client.post(
        "/recruitment/job-requisitions",
        json={
            "code": f"REQ-{suffix}",
            "title": "Backend Engineer",
            "organization_id": organization["id"],
            "department_id": department["id"],
            "position_id": position["id"],
            "status": "open",
        },
        headers=headers,
    ).json()
    response = client.post(
        "/recruitment/applications",
        json={
            "candidate_id": candidate["id"],
            "job_requisition_id": job_requisition["id"],
            "applied_date": "2026-01-01",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_interview(
    client: TestClient, headers: dict[str, str], *, application_id: str, **overrides
) -> dict:
    body = {
        "application_id": application_id,
        "scheduled_at": "2026-02-01T10:00:00Z",
        **overrides,
    }
    response = client.post("/recruitment/interviews", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_interview_requires_authentication(client: TestClient):
    response = client.post(
        "/recruitment/interviews",
        json={"application_id": str(uuid.uuid4()), "scheduled_at": "2026-02-01T10:00:00Z"},
    )

    assert response.status_code == 401


def test_list_interviews_requires_authentication(client: TestClient):
    assert client.get("/recruitment/interviews").status_code == 401


def test_get_interview_requires_authentication(client: TestClient):
    assert client.get(f"/recruitment/interviews/{uuid.uuid4()}").status_code == 401


def test_update_interview_requires_authentication(client: TestClient):
    response = client.put(f"/recruitment/interviews/{uuid.uuid4()}", json={"notes": "x"})
    assert response.status_code == 401


def test_delete_interview_requires_authentication(client: TestClient):
    assert client.delete(f"/recruitment/interviews/{uuid.uuid4()}").status_code == 401


def test_create_interview_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.post(
        "/recruitment/interviews",
        json={"application_id": str(uuid.uuid4()), "scheduled_at": "2026-02-01T10:00:00Z"},
        headers=member_headers,
    )

    assert response.status_code == 403


def test_list_interviews_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    assert client.get("/recruitment/interviews", headers=member_headers).status_code == 403


def test_get_interview_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/recruitment/interviews/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_update_interview_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/interviews/{uuid.uuid4()}", json={"notes": "x"}, headers=member_headers
    )
    assert response.status_code == 403


def test_delete_interview_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.delete(f"/recruitment/interviews/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_create_interview(client: TestClient, admin_headers: dict[str, str]):
    application_id = _create_application(client, admin_headers)

    body = _create_interview(
        client, admin_headers, application_id=application_id, notes="First round"
    )

    assert body["application_id"] == application_id
    assert body["notes"] == "First round"
    uuid.UUID(body["id"])


def test_create_interview_rejects_missing_application(
    client: TestClient, admin_headers: dict[str, str]
):
    response = client.post(
        "/recruitment/interviews",
        json={"application_id": str(uuid.uuid4()), "scheduled_at": "2026-02-01T10:00:00Z"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_get_interview(client: TestClient, admin_headers: dict[str, str]):
    application_id = _create_application(client, admin_headers)
    created = _create_interview(client, admin_headers, application_id=application_id)

    response = client.get(f"/recruitment/interviews/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_interview_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(f"/recruitment/interviews/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404


def test_list_interviews_paginated(client: TestClient, admin_headers: dict[str, str]):
    application_id = _create_application(client, admin_headers)
    _create_interview(client, admin_headers, application_id=application_id)

    response = client.get("/recruitment/interviews/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_interview(client: TestClient, admin_headers: dict[str, str]):
    application_id = _create_application(client, admin_headers)
    created = _create_interview(client, admin_headers, application_id=application_id)

    response = client.put(
        f"/recruitment/interviews/{created['id']}",
        json={"notes": "Rescheduled"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Rescheduled"


def test_update_interview_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/interviews/{uuid.uuid4()}", json={"notes": "x"}, headers=admin_headers
    )
    assert response.status_code == 404


def test_delete_interview(client: TestClient, admin_headers: dict[str, str]):
    application_id = _create_application(client, admin_headers)
    created = _create_interview(client, admin_headers, application_id=application_id)

    response = client.delete(f"/recruitment/interviews/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/recruitment/interviews/{created['id']}", headers=admin_headers).status_code
        == 404
    )


def test_delete_interview_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/recruitment/interviews/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404
