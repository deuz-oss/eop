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
# `test_payroll_runs_api.py`'s exact fixture/test pattern -- the only
# precedent for a Role Based (non-Owner-Only) protected resource in this
# repository.


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


def test_list_job_requisitions_requires_authentication(client: TestClient):
    response = client.get("/recruitment/job-requisitions")

    assert response.status_code == 401


def test_get_job_requisition_requires_authentication(client: TestClient):
    response = client.get(f"/recruitment/job-requisitions/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_job_requisition_requires_authentication(client: TestClient):
    response = client.put(
        f"/recruitment/job-requisitions/{uuid.uuid4()}", json={"status": "closed"}
    )

    assert response.status_code == 401


def test_delete_job_requisition_requires_authentication(client: TestClient):
    response = client.delete(f"/recruitment/job-requisitions/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_job_requisition_rejects_non_admin(
    client: TestClient, member_headers: dict[str, str]
):
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
        headers=member_headers,
    )

    assert response.status_code == 403


def test_list_job_requisitions_rejects_non_admin(
    client: TestClient, member_headers: dict[str, str]
):
    response = client.get("/recruitment/job-requisitions", headers=member_headers)

    assert response.status_code == 403


def test_list_job_requisitions_paginated_rejects_non_admin(
    client: TestClient, member_headers: dict[str, str]
):
    response = client.get("/recruitment/job-requisitions/paginated", headers=member_headers)

    assert response.status_code == 403


def test_get_job_requisition_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/recruitment/job-requisitions/{uuid.uuid4()}", headers=member_headers)

    assert response.status_code == 403


def test_update_job_requisition_rejects_non_admin(
    client: TestClient, member_headers: dict[str, str]
):
    response = client.put(
        f"/recruitment/job-requisitions/{uuid.uuid4()}",
        json={"status": "closed"},
        headers=member_headers,
    )

    assert response.status_code == 403


def test_delete_job_requisition_rejects_non_admin(
    client: TestClient, member_headers: dict[str, str]
):
    response = client.delete(
        f"/recruitment/job-requisitions/{uuid.uuid4()}", headers=member_headers
    )

    assert response.status_code == 403


def test_create_job_requisition(client: TestClient, admin_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, admin_headers)

    body = _create_job_requisition(
        client,
        admin_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
    )

    assert body["code"] == "REQ-1"
    assert body["title"] == "Backend Engineer"
    assert body["status"] == "open"
    uuid.UUID(body["id"])


def test_create_job_requisition_rejects_duplicate_code(
    client: TestClient, admin_headers: dict[str, str]
):
    organization_id, department_id, position_id = _create_org_dept_position(client, admin_headers)
    _create_job_requisition(
        client,
        admin_headers,
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
        headers=admin_headers,
    )

    assert response.status_code == 409


def test_create_job_requisition_rejects_missing_organization(
    client: TestClient, admin_headers: dict[str, str]
):
    _, department_id, position_id = _create_org_dept_position(client, admin_headers)

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
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_get_job_requisition(client: TestClient, admin_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, admin_headers)
    created = _create_job_requisition(
        client,
        admin_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
    )

    response = client.get(f"/recruitment/job-requisitions/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["code"] == "REQ-1"


def test_get_job_requisition_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(f"/recruitment/job-requisitions/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_list_job_requisitions_paginated(client: TestClient, admin_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, admin_headers)
    for i in range(3):
        _create_job_requisition(
            client,
            admin_headers,
            organization_id=organization_id,
            department_id=department_id,
            position_id=position_id,
            code=f"REQ-{i}",
        )

    response = client.get("/recruitment/job-requisitions/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 3


def test_update_job_requisition(client: TestClient, admin_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, admin_headers)
    created = _create_job_requisition(
        client,
        admin_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
    )

    response = client.put(
        f"/recruitment/job-requisitions/{created['id']}",
        json={"status": "closed"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "closed"


def test_update_job_requisition_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/recruitment/job-requisitions/{uuid.uuid4()}",
        json={"status": "closed"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_delete_job_requisition(client: TestClient, admin_headers: dict[str, str]):
    organization_id, department_id, position_id = _create_org_dept_position(client, admin_headers)
    created = _create_job_requisition(
        client,
        admin_headers,
        organization_id=organization_id,
        department_id=department_id,
        position_id=position_id,
    )

    response = client.delete(
        f"/recruitment/job-requisitions/{created['id']}", headers=admin_headers
    )

    assert response.status_code == 204
    assert (
        client.get(
            f"/recruitment/job-requisitions/{created['id']}", headers=admin_headers
        ).status_code
        == 404
    )


def test_delete_job_requisition_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/recruitment/job-requisitions/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404
