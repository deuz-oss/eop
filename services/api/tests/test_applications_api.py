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
# `test_payroll_runs_api.py`'s exact fixture/test pattern.


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
    """Grants the `admin` role directly at the DB layer, mirroring
    `test_payroll_runs_api.py`'s `_seed_admin`."""
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
    """An authenticated user without the `admin` role."""
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def member_headers(client: TestClient, member_user: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_candidate(client: TestClient, headers: dict[str, str]) -> str:
    suffix = uuid.uuid4().hex[:8]
    response = client.post(
        "/recruitment/candidates",
        json={
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "email": f"ada-{suffix}@example.com",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_job_requisition(client: TestClient, headers: dict[str, str]) -> str:
    suffix = uuid.uuid4().hex[:8]
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
    response = client.post(
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
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_application(
    client: TestClient,
    headers: dict[str, str],
    *,
    candidate_id: str,
    job_requisition_id: str,
    **overrides,
) -> dict:
    body = {
        "candidate_id": candidate_id,
        "job_requisition_id": job_requisition_id,
        "status": "applied",
        "applied_date": "2026-01-01",
        **overrides,
    }
    response = client.post("/recruitment/applications", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_application_requires_authentication(client: TestClient):
    response = client.post(
        "/recruitment/applications",
        json={
            "candidate_id": str(uuid.uuid4()),
            "job_requisition_id": str(uuid.uuid4()),
            "status": "applied",
            "applied_date": "2026-01-01",
        },
    )

    assert response.status_code == 401


def test_list_applications_requires_authentication(client: TestClient):
    response = client.get("/recruitment/applications")

    assert response.status_code == 401


def test_get_application_requires_authentication(client: TestClient):
    response = client.get(f"/recruitment/applications/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_application_requires_authentication(client: TestClient):
    response = client.put(
        f"/recruitment/applications/{uuid.uuid4()}", json={"status": "interviewing"}
    )

    assert response.status_code == 401


def test_delete_application_requires_authentication(client: TestClient):
    response = client.delete(f"/recruitment/applications/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_application_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.post(
        "/recruitment/applications",
        json={
            "candidate_id": str(uuid.uuid4()),
            "job_requisition_id": str(uuid.uuid4()),
            "status": "applied",
            "applied_date": "2026-01-01",
        },
        headers=member_headers,
    )

    assert response.status_code == 403


def test_list_applications_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get("/recruitment/applications", headers=member_headers)

    assert response.status_code == 403


def test_list_applications_paginated_rejects_non_admin(
    client: TestClient, member_headers: dict[str, str]
):
    response = client.get("/recruitment/applications/paginated", headers=member_headers)

    assert response.status_code == 403


def test_get_application_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/recruitment/applications/{uuid.uuid4()}", headers=member_headers)

    assert response.status_code == 403


def test_update_application_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/applications/{uuid.uuid4()}",
        json={"status": "interviewing"},
        headers=member_headers,
    )

    assert response.status_code == 403


def test_delete_application_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.delete(f"/recruitment/applications/{uuid.uuid4()}", headers=member_headers)

    assert response.status_code == 403


def test_create_application(client: TestClient, admin_headers: dict[str, str]):
    candidate_id = _create_candidate(client, admin_headers)
    job_requisition_id = _create_job_requisition(client, admin_headers)

    body = _create_application(
        client, admin_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    assert body["candidate_id"] == candidate_id
    assert body["job_requisition_id"] == job_requisition_id
    assert body["status"] == "applied"
    uuid.UUID(body["id"])


def test_create_application_rejects_missing_candidate(
    client: TestClient, admin_headers: dict[str, str]
):
    job_requisition_id = _create_job_requisition(client, admin_headers)

    response = client.post(
        "/recruitment/applications",
        json={
            "candidate_id": str(uuid.uuid4()),
            "job_requisition_id": job_requisition_id,
            "status": "applied",
            "applied_date": "2026-01-01",
        },
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_create_application_rejects_duplicate(client: TestClient, admin_headers: dict[str, str]):
    candidate_id = _create_candidate(client, admin_headers)
    job_requisition_id = _create_job_requisition(client, admin_headers)
    _create_application(
        client, admin_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.post(
        "/recruitment/applications",
        json={
            "candidate_id": candidate_id,
            "job_requisition_id": job_requisition_id,
            "status": "applied",
            "applied_date": "2026-01-02",
        },
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_get_application(client: TestClient, admin_headers: dict[str, str]):
    candidate_id = _create_candidate(client, admin_headers)
    job_requisition_id = _create_job_requisition(client, admin_headers)
    created = _create_application(
        client, admin_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.get(f"/recruitment/applications/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_application_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(f"/recruitment/applications/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_list_applications_paginated(client: TestClient, admin_headers: dict[str, str]):
    candidate_id = _create_candidate(client, admin_headers)
    job_requisition_id = _create_job_requisition(client, admin_headers)
    _create_application(
        client, admin_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.get("/recruitment/applications/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_application(client: TestClient, admin_headers: dict[str, str]):
    candidate_id = _create_candidate(client, admin_headers)
    job_requisition_id = _create_job_requisition(client, admin_headers)
    created = _create_application(
        client, admin_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.put(
        f"/recruitment/applications/{created['id']}",
        json={"status": "interviewing"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "interviewing"


def test_update_application_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/applications/{uuid.uuid4()}",
        json={"status": "interviewing"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_delete_application(client: TestClient, admin_headers: dict[str, str]):
    candidate_id = _create_candidate(client, admin_headers)
    job_requisition_id = _create_job_requisition(client, admin_headers)
    created = _create_application(
        client, admin_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.delete(f"/recruitment/applications/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/recruitment/applications/{created['id']}", headers=admin_headers).status_code
        == 404
    )


def test_delete_application_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/recruitment/applications/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404
