import asyncio
import uuid
from collections.abc import Generator

import pytest
from conftest import clean_database
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository

_tables = pytest.fixture(autouse=True)(clean_database)


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
def other() -> User:
    """An authenticated user who does not own the compensation under test."""
    return asyncio.run(_create_user(email="other@example.com", password="other-pass"))


@pytest.fixture
def other_headers(client: TestClient, other: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "other-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_organization(client: TestClient, headers: dict[str, str], *, name: str) -> dict:
    response = client.post("/organizations", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()


def _create_department(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Engineering",
    code: str,
    organization_id: str,
) -> dict:
    response = client.post(
        "/departments",
        json={"name": name, "code": code, "organization_id": organization_id},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_position(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Engineer",
    code: str,
    organization_id: str,
    department_id: str,
) -> dict:
    response = client.post(
        "/positions",
        json={
            "name": name,
            "code": code,
            "organization_id": organization_id,
            "department_id": department_id,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_team(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Backend Team",
    code: str,
    organization_id: str,
    department_id: str,
) -> dict:
    response = client.post(
        "/teams",
        json={
            "name": name,
            "code": code,
            "organization_id": organization_id,
            "department_id": department_id,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


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


def _create_location_type(
    client: TestClient, headers: dict[str, str], *, name: str = "Office", code: str
) -> dict:
    response = client.post("/location-types", json={"name": name, "code": code}, headers=headers)
    assert response.status_code == 201
    return response.json()


def _create_location(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "HQ",
    code: str,
    location_type_id: str,
) -> dict:
    response = client.post(
        "/locations",
        json={"name": name, "code": code, "location_type_id": location_type_id},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_job_grade(
    client: TestClient, headers: dict[str, str], *, name: str = "Engineer I", code: str, level: int
) -> dict:
    response = client.post(
        "/hr/job-grades", json={"name": name, "code": code, "level": level}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_employment_type(
    client: TestClient, headers: dict[str, str], *, name: str = "Full-Time", code: str
) -> dict:
    response = client.post(
        "/hr/employment-types", json={"name": name, "code": code}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_employment_status(
    client: TestClient, headers: dict[str, str], *, name: str = "Active", code: str
) -> dict:
    response = client.post(
        "/hr/employment-statuses", json={"name": name, "code": code}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_shift(
    client: TestClient, headers: dict[str, str], *, name: str = "Day Shift", code: str
) -> dict:
    response = client.post(
        "/hr/shifts",
        json={"code": code, "name": name, "start_time": "09:00:00", "end_time": "17:00:00"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_employee(
    client: TestClient, headers: dict[str, str], *, user_id: str | None = None
) -> dict:
    """Creates its own HR master-data scaffolding, suffixed by a fresh id so
    multiple employees (e.g. owner + non-owner) can be created within the
    same test without violating `code`/`name` uniqueness constraints.
    Mirrors `test_attendance_events_api.py`'s `_create_employee` helper."""
    suffix = uuid.uuid4().hex[:8]
    organization = _create_organization(client, headers, name=f"Acme Corp {suffix}")
    department = _create_department(
        client, headers, organization_id=organization["id"], code=f"ENG-{suffix}"
    )
    position = _create_position(
        client,
        headers,
        organization_id=organization["id"],
        department_id=department["id"],
        code=f"POS-{suffix}",
    )
    team = _create_team(
        client,
        headers,
        organization_id=organization["id"],
        department_id=department["id"],
        code=f"TEAM-{suffix}",
    )
    location_admin_headers = _location_admin_headers(client)
    location_type = _create_location_type(client, location_admin_headers, code=f"OFFICE-{suffix}")
    location = _create_location(
        client, location_admin_headers, location_type_id=location_type["id"], code=f"HQ-{suffix}"
    )
    job_grade = _create_job_grade(
        client, location_admin_headers, code=f"L1-{suffix}", level=int(suffix[:4], 16) + 1
    )
    employment_type = _create_employment_type(client, location_admin_headers, code=f"FT-{suffix}")
    employment_status = _create_employment_status(
        client, location_admin_headers, code=f"ACTIVE-{suffix}"
    )
    shift = _create_shift(client, location_admin_headers, code=f"DAY-{suffix}")

    payload = {
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
    }
    if user_id is not None:
        payload["user_id"] = user_id

    response = client.post("/hr/employees", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def _create_compensation(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_id: str,
    base_salary_amount: str = "1000.00",
    base_salary_currency: str = "IDR",
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    corrects_id: str | None = None,
) -> dict:
    payload = {
        "employee_id": employee_id,
        "base_salary_amount": base_salary_amount,
        "base_salary_currency": base_salary_currency,
        "effective_from": effective_from,
    }
    if effective_to is not None:
        payload["effective_to"] = effective_to
    if corrects_id is not None:
        payload["corrects_id"] = corrects_id
    response = client.post("/hr/compensation", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_compensation_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": str(uuid.uuid4()),
            "base_salary_amount": "1000.00",
            "base_salary_currency": "IDR",
            "effective_from": "2026-01-01",
        },
    )

    assert response.status_code == 401


def test_create_compensation(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    body = _create_compensation(client, user_headers, employee_id=employee["id"])

    assert body["employee_id"] == employee["id"]
    assert body["base_salary_amount"] == "1000.00"
    assert body["base_salary_currency"] == "IDR"
    assert body["is_active"] is True
    uuid.UUID(body["id"])


def test_create_compensation_normalizes_precision(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    body = _create_compensation(
        client, user_headers, employee_id=employee["id"], base_salary_amount="10.125"
    )

    assert body["base_salary_amount"] == "10.13"


def test_create_compensation_rejects_missing_employee(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": str(uuid.uuid4()),
            "base_salary_amount": "1000.00",
            "base_salary_currency": "IDR",
            "effective_from": "2026-01-01",
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_compensation_allows_multiple_historical_rows(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    """`docs/architecture/capabilities/compensation/decision.md` §17 (Accepted):
    multiple Compensation rows may exist per employee."""
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    first = _create_compensation(
        client,
        user_headers,
        employee_id=employee["id"],
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )

    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": employee["id"],
            "base_salary_amount": "2000.00",
            "base_salary_currency": "IDR",
            "effective_from": "2026-07-01",
        },
        headers=user_headers,
    )

    assert response.status_code == 201
    assert response.json()["id"] != first["id"]


def test_create_compensation_rejects_overlapping_period(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    """§19, Option O1 (Accepted): overlapping periods for the same
    employee are rejected -- maps to 409, the project's standard conflict
    response."""
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_compensation(
        client,
        user_headers,
        employee_id=employee["id"],
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )

    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": employee["id"],
            "base_salary_amount": "2000.00",
            "base_salary_currency": "IDR",
            "effective_from": "2026-03-01",
        },
        headers=user_headers,
    )

    assert response.status_code == 409


def test_create_compensation_correction(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    target = _create_compensation(
        client,
        user_headers,
        employee_id=employee["id"],
        base_salary_amount="1000.00",
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )

    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": employee["id"],
            "base_salary_amount": "1100.00",
            "base_salary_currency": "IDR",
            "effective_from": "2026-01-01",
            "effective_to": "2026-06-30",
            "corrects_id": target["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["corrects_id"] == target["id"]
    assert body["id"] != target["id"]


def test_create_compensation_correction_invalid_target(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": employee["id"],
            "base_salary_amount": "1000.00",
            "base_salary_currency": "IDR",
            "effective_from": "2026-01-01",
            "corrects_id": str(uuid.uuid4()),
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_compensation_response_contains_effective_to_and_corrects_id(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    body = _create_compensation(
        client,
        user_headers,
        employee_id=employee["id"],
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )

    assert body["effective_to"] == "2026-06-30"
    assert body["corrects_id"] is None


def test_create_compensation_rejects_empty_currency(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": employee["id"],
            "base_salary_amount": "1000.00",
            "base_salary_currency": "",
            "effective_from": "2026-01-01",
        },
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_compensation_forbidden_for_non_owner(
    client: TestClient, user_headers: dict[str, str], other: User, other_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": employee["id"],
            "base_salary_amount": "1000.00",
            "base_salary_currency": "IDR",
            "effective_from": "2026-01-01",
        },
        headers=other_headers,
    )

    assert response.status_code == 403


def test_get_compensation(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_compensation(client, user_headers, employee_id=employee["id"])

    response = client.get(f"/hr/compensation/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_compensation_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.get(f"/hr/compensation/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_get_compensation_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_compensation(client, user_headers, employee_id=employee["id"])
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.get(f"/hr/compensation/{created['id']}", headers=other_headers)

    assert response.status_code == 403


def test_get_compensation_by_employee(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_compensation(client, user_headers, employee_id=employee["id"])

    response = client.get(f"/hr/compensation/by-employee/{employee['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_compensation_by_employee_resolves_as_of_date(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    earlier = _create_compensation(
        client,
        user_headers,
        employee_id=employee["id"],
        base_salary_amount="1000.00",
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )
    response = client.post(
        "/hr/compensation",
        json={
            "employee_id": employee["id"],
            "base_salary_amount": "1200.00",
            "base_salary_currency": "IDR",
            "effective_from": "2026-07-01",
        },
        headers=user_headers,
    )
    assert response.status_code == 201

    response = client.get(
        f"/hr/compensation/by-employee/{employee['id']}",
        params={"as_of": "2026-03-01"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == earlier["id"]


def test_get_compensation_by_employee_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_compensation(client, user_headers, employee_id=employee["id"])
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.get(f"/hr/compensation/by-employee/{employee['id']}", headers=other_headers)

    assert response.status_code == 403


def test_list_compensation_returns_only_owned(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(client, user_headers, user_id=str(other.id))
    _create_compensation(client, user_headers, employee_id=employee["id"])
    _create_compensation(client, other_headers, employee_id=other_employee["id"])

    response = client.get("/hr/compensation", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["employee_id"] == employee["id"]


def test_update_compensation_only_changes_is_active(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    """`CompensationUpdate` carries only `is_active`
    (`docs/architecture/capabilities/compensation/decision.md` §18, Option A3) --
    `base_salary_amount` cannot be changed via `PUT`, since that would mutate
    a historical fact in place; unrecognized fields are ignored, not applied."""
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_compensation(client, user_headers, employee_id=employee["id"])

    response = client.put(
        f"/hr/compensation/{created['id']}",
        json={"base_salary_amount": "1500.00", "is_active": False},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["base_salary_amount"] == created["base_salary_amount"]
    assert response.json()["is_active"] is False

    listed = client.get("/hr/compensation", headers=user_headers)
    assert len(listed.json()) == 1


def test_update_compensation_not_found(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.put(
        f"/hr/compensation/{uuid.uuid4()}",
        json={"base_salary_amount": "1500.00"},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_compensation_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_compensation(client, user_headers, employee_id=employee["id"])
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.put(
        f"/hr/compensation/{created['id']}",
        json={"base_salary_amount": "1500.00"},
        headers=other_headers,
    )

    assert response.status_code == 403


def test_delete_compensation_leaf_row_rejected(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    """Compensation Delete Integrity: an uncorrected/leaf row is rejected
    with 409, and the row is left untouched."""
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_compensation(client, user_headers, employee_id=employee["id"])

    response = client.delete(f"/hr/compensation/{created['id']}", headers=user_headers)

    assert response.status_code == 409
    assert client.get(f"/hr/compensation/{created['id']}", headers=user_headers).status_code == 200


def test_delete_compensation_already_referenced_by_correction_rejected(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    """A row already referenced by another row's `corrects_id` is rejected
    the same clean 409 way, not a raw `IntegrityError`/500."""
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    target = _create_compensation(
        client,
        user_headers,
        employee_id=employee["id"],
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )
    _create_compensation(
        client,
        user_headers,
        employee_id=employee["id"],
        effective_from="2026-01-01",
        effective_to="2026-06-30",
        corrects_id=target["id"],
    )

    response = client.delete(f"/hr/compensation/{target['id']}", headers=user_headers)

    assert response.status_code == 409
    assert client.get(f"/hr/compensation/{target['id']}", headers=user_headers).status_code == 200


def test_delete_compensation_not_found(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.delete(f"/hr/compensation/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_delete_compensation_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_compensation(client, user_headers, employee_id=employee["id"])
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.delete(f"/hr/compensation/{created['id']}", headers=other_headers)

    assert response.status_code == 403
