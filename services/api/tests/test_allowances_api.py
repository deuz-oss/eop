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
def user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


@pytest.fixture
def user_headers(client: TestClient, user: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "member@example.com", "password": "member-pass"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def other() -> User:
    return asyncio.run(_create_user(email="other@example.com", password="other-pass"))


@pytest.fixture
def other_headers(client: TestClient, other: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "other-pass"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _seed_location_admin(user_id: uuid.UUID) -> None:
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


def _location_admin_headers(client: TestClient) -> dict[str, str]:
    """A throwaway admin session used only to satisfy the admin-only
    Location/LocationType write requirement during master-data bootstrap --
    the employee/user actually under test keeps its own identity."""
    suffix = uuid.uuid4().hex[:8]
    email = f"location-admin-{suffix}@example.com"
    user = asyncio.run(_create_user(email=email, password="admin-pass"))
    asyncio.run(_seed_location_admin(user.id))
    response = client.post("/auth/login", json={"email": email, "password": "admin-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _create_employee(client: TestClient, headers: dict[str, str], *, user_id: str) -> dict:
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
    location_admin_headers = _location_admin_headers(client)
    location_type = client.post(
        "/location-types",
        json={"name": "Office", "code": f"OFFICE-{suffix}"},
        headers=location_admin_headers,
    ).json()
    location = client.post(
        "/locations",
        json={"name": "HQ", "code": f"HQ-{suffix}", "location_type_id": location_type["id"]},
        headers=location_admin_headers,
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
            "user_id": user_id,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_allowance(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_id: str,
    allowance_type: str = "TRANSPORT",
) -> dict:
    response = client.post(
        "/hr/allowances",
        json={
            "employee_id": employee_id,
            "allowance_type": allowance_type,
            "allowance_amount": "500000.00",
            "allowance_currency": "IDR",
            "effective_from": "2026-01-01",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_allowance_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/allowances",
        json={
            "employee_id": str(uuid.uuid4()),
            "allowance_type": "TRANSPORT",
            "allowance_amount": "500000.00",
            "allowance_currency": "IDR",
            "effective_from": "2026-01-01",
        },
    )

    assert response.status_code == 401


def test_create_and_get_allowance(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    created = _create_allowance(client, user_headers, employee_id=employee["id"])

    response = client.get(f"/hr/allowances/{created['id']}", headers=user_headers)
    assert response.status_code == 200
    assert response.json()["allowance_amount"] == "500000.00"


def test_create_allowance_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    # `other` needs its own linked HrEmployee for `CurrentRequestContext` to
    # resolve at all -- otherwise the request never reaches authorization,
    # it fails earlier with `EmployeeContextNotFoundError`.
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.post(
        "/hr/allowances",
        json={
            "employee_id": employee["id"],
            "allowance_type": "TRANSPORT",
            "allowance_amount": "500000.00",
            "allowance_currency": "IDR",
            "effective_from": "2026-01-01",
        },
        headers=other_headers,
    )

    assert response.status_code == 403


def test_create_allowance_rejects_overlapping_period_same_type(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_allowance(client, user_headers, employee_id=employee["id"])

    response = client.post(
        "/hr/allowances",
        json={
            "employee_id": employee["id"],
            "allowance_type": "TRANSPORT",
            "allowance_amount": "500000.00",
            "allowance_currency": "IDR",
            "effective_from": "2026-02-01",
        },
        headers=user_headers,
    )

    assert response.status_code == 409


def test_create_allowance_allows_different_type_same_period(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_allowance(client, user_headers, employee_id=employee["id"], allowance_type="TRANSPORT")

    response = client.post(
        "/hr/allowances",
        json={
            "employee_id": employee["id"],
            "allowance_type": "MEAL",
            "allowance_amount": "300000.00",
            "allowance_currency": "IDR",
            "effective_from": "2026-01-01",
        },
        headers=user_headers,
    )

    assert response.status_code == 201


def test_update_allowance_deactivate(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_allowance(client, user_headers, employee_id=employee["id"])

    response = client.put(
        f"/hr/allowances/{created['id']}", json={"is_active": False}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False


def test_delete_allowance(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_allowance(client, user_headers, employee_id=employee["id"])

    response = client.delete(f"/hr/allowances/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/hr/allowances/{created['id']}", headers=user_headers).status_code == 404


def test_list_allowances_returns_only_owned(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(client, user_headers, user_id=str(other.id))
    _create_allowance(client, user_headers, employee_id=employee["id"])
    _create_allowance(client, other_headers, employee_id=other_employee["id"])

    response = client.get("/hr/allowances", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["employee_id"] == employee["id"]
