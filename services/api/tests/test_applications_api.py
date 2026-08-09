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
def user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def user_headers(client: TestClient, user: User) -> dict[str, str]:
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


def test_create_application(client: TestClient, user_headers: dict[str, str]):
    candidate_id = _create_candidate(client, user_headers)
    job_requisition_id = _create_job_requisition(client, user_headers)

    body = _create_application(
        client, user_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    assert body["candidate_id"] == candidate_id
    assert body["job_requisition_id"] == job_requisition_id
    assert body["status"] == "applied"
    uuid.UUID(body["id"])


def test_create_application_rejects_missing_candidate(
    client: TestClient, user_headers: dict[str, str]
):
    job_requisition_id = _create_job_requisition(client, user_headers)

    response = client.post(
        "/recruitment/applications",
        json={
            "candidate_id": str(uuid.uuid4()),
            "job_requisition_id": job_requisition_id,
            "status": "applied",
            "applied_date": "2026-01-01",
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_application_rejects_duplicate(client: TestClient, user_headers: dict[str, str]):
    candidate_id = _create_candidate(client, user_headers)
    job_requisition_id = _create_job_requisition(client, user_headers)
    _create_application(
        client, user_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.post(
        "/recruitment/applications",
        json={
            "candidate_id": candidate_id,
            "job_requisition_id": job_requisition_id,
            "status": "applied",
            "applied_date": "2026-01-02",
        },
        headers=user_headers,
    )

    assert response.status_code == 409


def test_get_application(client: TestClient, user_headers: dict[str, str]):
    candidate_id = _create_candidate(client, user_headers)
    job_requisition_id = _create_job_requisition(client, user_headers)
    created = _create_application(
        client, user_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.get(f"/recruitment/applications/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_application_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/recruitment/applications/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_applications_paginated(client: TestClient, user_headers: dict[str, str]):
    candidate_id = _create_candidate(client, user_headers)
    job_requisition_id = _create_job_requisition(client, user_headers)
    _create_application(
        client, user_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.get("/recruitment/applications/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_application(client: TestClient, user_headers: dict[str, str]):
    candidate_id = _create_candidate(client, user_headers)
    job_requisition_id = _create_job_requisition(client, user_headers)
    created = _create_application(
        client, user_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.put(
        f"/recruitment/applications/{created['id']}",
        json={"status": "interviewing"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "interviewing"


def test_update_application_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/applications/{uuid.uuid4()}",
        json={"status": "interviewing"},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_delete_application(client: TestClient, user_headers: dict[str, str]):
    candidate_id = _create_candidate(client, user_headers)
    job_requisition_id = _create_job_requisition(client, user_headers)
    created = _create_application(
        client, user_headers, candidate_id=candidate_id, job_requisition_id=job_requisition_id
    )

    response = client.delete(f"/recruitment/applications/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/recruitment/applications/{created['id']}", headers=user_headers).status_code
        == 404
    )


def test_delete_application_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/recruitment/applications/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404
