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


def _create_org_dept_position(client: TestClient, headers: dict[str, str]) -> tuple[str, str, str]:
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
    return organization["id"], department["id"], position["id"]


def _create_job_requisition(
    client: TestClient,
    headers: dict[str, str],
    *,
    organization_id: str,
    department_id: str,
    position_id: str,
    code: str = "REQ-1",
    **overrides,
) -> dict:
    body = {
        "code": code,
        "title": "Backend Engineer",
        "organization_id": organization_id,
        "department_id": department_id,
        "position_id": position_id,
        "status": "open",
        **overrides,
    }
    response = client.post("/recruitment/job-requisitions", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_job_requisition_requires_authentication(client: TestClient):
    response = client.post(
        "/recruitment/job-requisitions",
        json={
            "code": "REQ-1",
            "title": "Backend Engineer",
            "organization_id": str(uuid.uuid4()),
            "department_id": str(uuid.uuid4()),
            "position_id": str(uuid.uuid4()),
            "status": "open",
        },
    )

    assert response.status_code == 401


def test_create_job_requisition(client: TestClient, user_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, user_headers)

    body = _create_job_requisition(
        client,
        user_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
    )

    assert body["code"] == "REQ-1"
    assert body["title"] == "Backend Engineer"
    assert body["status"] == "open"
    uuid.UUID(body["id"])


def test_create_job_requisition_rejects_duplicate_code(
    client: TestClient, user_headers: dict[str, str]
):
    organization_id, department_id, position_id = _create_org_dept_position(client, user_headers)
    _create_job_requisition(
        client,
        user_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
        code="REQ-1",
    )

    response = client.post(
        "/recruitment/job-requisitions",
        json={
            "code": "REQ-1",
            "title": "Other",
            "organization_id": organization_id,
            "department_id": department_id,
            "position_id": position_id,
            "status": "open",
        },
        headers=user_headers,
    )

    assert response.status_code == 409


def test_create_job_requisition_rejects_missing_organization(
    client: TestClient, user_headers: dict[str, str]
):
    _, department_id, position_id = _create_org_dept_position(client, user_headers)

    response = client.post(
        "/recruitment/job-requisitions",
        json={
            "code": "REQ-1",
            "title": "Backend Engineer",
            "organization_id": str(uuid.uuid4()),
            "department_id": department_id,
            "position_id": position_id,
            "status": "open",
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_get_job_requisition(client: TestClient, user_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, user_headers)
    created = _create_job_requisition(
        client,
        user_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
    )

    response = client.get(f"/recruitment/job-requisitions/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["code"] == "REQ-1"


def test_get_job_requisition_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/recruitment/job-requisitions/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_job_requisitions_paginated(client: TestClient, user_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, user_headers)
    for i in range(3):
        _create_job_requisition(
            client,
            user_headers,
            organization_id=organization_id,
            department_id=department_id,
            position_id=position_id,
            code=f"REQ-{i}",
        )

    response = client.get("/recruitment/job-requisitions/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_update_job_requisition(client: TestClient, user_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, user_headers)
    created = _create_job_requisition(
        client,
        user_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
    )

    response = client.put(
        f"/recruitment/job-requisitions/{created['id']}",
        json={"status": "closed"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_update_job_requisition_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/job-requisitions/{uuid.uuid4()}",
        json={"status": "closed"},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_delete_job_requisition(client: TestClient, user_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, user_headers)
    created = _create_job_requisition(
        client,
        user_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
    )

    response = client.delete(f"/recruitment/job-requisitions/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert (
        client.get(
            f"/recruitment/job-requisitions/{created['id']}", headers=user_headers
        ).status_code
        == 404
    )


def test_delete_job_requisition_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/recruitment/job-requisitions/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404
