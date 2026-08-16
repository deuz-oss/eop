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

# Performance Authorization: Role Based (`RequireRole("admin")`), mirroring
# `test_payroll_runs_api.py`'s exact fixture/test pattern -- reused
# unmodified per explicit CPO/CTO instruction for Iteration 1.


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
            await conn.execute(
                text(
                    "TRUNCATE TABLE organizations, locations, location_types, "
                    "job_grades, employment_types, employment_statuses, shifts, users CASCADE"
                )
            )
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


def _create_employee(client: TestClient, headers: dict[str, str]) -> str:
    suffix = uuid.uuid4().hex[:8]
    organization = client.post(
        "/organizations", json={"name": f"Acme {suffix}"}, headers=headers
    ).json()
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
    team = client.post(
        "/teams",
        json={
            "name": "Backend",
            "code": f"TEAM-{suffix}",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=headers,
    ).json()
    location_type = client.post(
        "/location-types", json={"name": "Office", "code": f"OFFICE-{suffix}"}, headers=headers
    ).json()
    location = client.post(
        "/locations",
        json={"name": "HQ", "code": f"HQ-{suffix}", "location_type_id": location_type["id"]},
        headers=headers,
    ).json()
    job_grade = client.post(
        "/hr/job-grades",
        json={"name": "Engineer I", "code": f"L1-{suffix}", "level": int(suffix[:4], 16) + 1},
        headers=headers,
    ).json()
    employment_type = client.post(
        "/hr/employment-types", json={"name": "Full-Time", "code": f"FT-{suffix}"}, headers=headers
    ).json()
    employment_status = client.post(
        "/hr/employment-statuses",
        json={"name": "Active", "code": f"ACTIVE-{suffix}"},
        headers=headers,
    ).json()
    shift = client.post(
        "/hr/shifts",
        json={
            "code": f"DAY-{suffix}",
            "name": "Day Shift",
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        },
        headers=headers,
    ).json()

    response = client.post(
        "/hr/employees",
        json={
            "employee_number": f"EMP-{suffix}",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "email": f"ada-{suffix}@example.com",
            "organization_id": organization["id"],
            "department_id": department["id"],
            "position_id": position["id"],
            "team_id": team["id"],
            "location_id": location["id"],
            "job_grade_id": job_grade["id"],
            "employment_type_id": employment_type["id"],
            "employment_status_id": employment_status["id"],
            "shift_id": shift["id"],
            "hire_date": "2024-01-15",
            "employment_status": "active",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_review(
    client: TestClient, headers: dict[str, str], *, employee_id: str, **overrides
) -> dict:
    body = {
        "employee_id": employee_id,
        "review_period_start": "2026-01-01",
        "review_period_end": "2026-06-30",
        **overrides,
    }
    response = client.post("/hr/performance-reviews", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_review_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/performance-reviews",
        json={
            "employee_id": str(uuid.uuid4()),
            "review_period_start": "2026-01-01",
            "review_period_end": "2026-06-30",
        },
    )

    assert response.status_code == 401


def test_list_reviews_requires_authentication(client: TestClient):
    assert client.get("/hr/performance-reviews").status_code == 401


def test_get_review_requires_authentication(client: TestClient):
    assert client.get(f"/hr/performance-reviews/{uuid.uuid4()}").status_code == 401


def test_update_review_requires_authentication(client: TestClient):
    response = client.put(f"/hr/performance-reviews/{uuid.uuid4()}", json={"notes": "x"})
    assert response.status_code == 401


def test_delete_review_requires_authentication(client: TestClient):
    assert client.delete(f"/hr/performance-reviews/{uuid.uuid4()}").status_code == 401


def test_create_review_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.post(
        "/hr/performance-reviews",
        json={
            "employee_id": str(uuid.uuid4()),
            "review_period_start": "2026-01-01",
            "review_period_end": "2026-06-30",
        },
        headers=member_headers,
    )

    assert response.status_code == 403


def test_list_reviews_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    assert client.get("/hr/performance-reviews", headers=member_headers).status_code == 403


def test_get_review_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/hr/performance-reviews/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_update_review_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.put(
        f"/hr/performance-reviews/{uuid.uuid4()}", json={"notes": "x"}, headers=member_headers
    )
    assert response.status_code == 403


def test_delete_review_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.delete(f"/hr/performance-reviews/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_create_review(client: TestClient, admin_headers: dict[str, str]):
    employee_id = _create_employee(client, admin_headers)

    body = _create_review(client, admin_headers, employee_id=employee_id, notes="Solid")

    assert body["employee_id"] == employee_id
    assert body["review_period_start"] == "2026-01-01"
    assert body["notes"] == "Solid"
    uuid.UUID(body["id"])


def test_create_review_rejects_missing_employee(client: TestClient, admin_headers: dict[str, str]):
    response = client.post(
        "/hr/performance-reviews",
        json={
            "employee_id": str(uuid.uuid4()),
            "review_period_start": "2026-01-01",
            "review_period_end": "2026-06-30",
        },
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_create_review_rejects_invalid_period(client: TestClient, admin_headers: dict[str, str]):
    employee_id = _create_employee(client, admin_headers)

    response = client.post(
        "/hr/performance-reviews",
        json={
            "employee_id": employee_id,
            "review_period_start": "2026-06-30",
            "review_period_end": "2026-01-01",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_get_review(client: TestClient, admin_headers: dict[str, str]):
    employee_id = _create_employee(client, admin_headers)
    created = _create_review(client, admin_headers, employee_id=employee_id)

    response = client.get(f"/hr/performance-reviews/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_review_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(f"/hr/performance-reviews/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404


def test_list_reviews_paginated(client: TestClient, admin_headers: dict[str, str]):
    employee_id = _create_employee(client, admin_headers)
    _create_review(client, admin_headers, employee_id=employee_id)

    response = client.get("/hr/performance-reviews/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_review(client: TestClient, admin_headers: dict[str, str]):
    employee_id = _create_employee(client, admin_headers)
    created = _create_review(client, admin_headers, employee_id=employee_id)

    response = client.put(
        f"/hr/performance-reviews/{created['id']}",
        json={"notes": "Updated"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Updated"


def test_update_review_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/hr/performance-reviews/{uuid.uuid4()}", json={"notes": "x"}, headers=admin_headers
    )
    assert response.status_code == 404


def test_delete_review(client: TestClient, admin_headers: dict[str, str]):
    employee_id = _create_employee(client, admin_headers)
    created = _create_review(client, admin_headers, employee_id=employee_id)

    response = client.delete(f"/hr/performance-reviews/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/hr/performance-reviews/{created['id']}", headers=admin_headers).status_code
        == 404
    )


def test_delete_review_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/hr/performance-reviews/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404


# --- Lifecycle (Iteration 2 D1, Approved: Option B, draft -> finalized) ---


def test_create_review_starts_draft(client: TestClient, admin_headers: dict[str, str]):
    employee_id = _create_employee(client, admin_headers)

    body = _create_review(client, admin_headers, employee_id=employee_id)

    assert body["status"] == "draft"


def test_finalize_review_requires_authentication(client: TestClient):
    response = client.post(f"/hr/performance-reviews/{uuid.uuid4()}/finalize")
    assert response.status_code == 401


def test_finalize_review_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.post(
        f"/hr/performance-reviews/{uuid.uuid4()}/finalize", headers=member_headers
    )
    assert response.status_code == 403


def test_finalize_review(client: TestClient, admin_headers: dict[str, str]):
    employee_id = _create_employee(client, admin_headers)
    created = _create_review(client, admin_headers, employee_id=employee_id)

    response = client.post(
        f"/hr/performance-reviews/{created['id']}/finalize", headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "finalized"


def test_finalize_review_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.post(
        f"/hr/performance-reviews/{uuid.uuid4()}/finalize", headers=admin_headers
    )
    assert response.status_code == 404


def test_finalize_review_rejects_already_finalized(
    client: TestClient, admin_headers: dict[str, str]
):
    employee_id = _create_employee(client, admin_headers)
    created = _create_review(client, admin_headers, employee_id=employee_id)
    client.post(f"/hr/performance-reviews/{created['id']}/finalize", headers=admin_headers)

    response = client.post(
        f"/hr/performance-reviews/{created['id']}/finalize", headers=admin_headers
    )

    assert response.status_code == 409


def test_update_finalized_review_rejects_substantive_change(
    client: TestClient, admin_headers: dict[str, str]
):
    employee_id = _create_employee(client, admin_headers)
    created = _create_review(client, admin_headers, employee_id=employee_id)
    client.post(f"/hr/performance-reviews/{created['id']}/finalize", headers=admin_headers)

    response = client.put(
        f"/hr/performance-reviews/{created['id']}",
        json={"notes": "Changed after finalize"},
        headers=admin_headers,
    )

    assert response.status_code == 409
