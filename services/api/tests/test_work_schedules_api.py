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
    """Ensures all tables exist and are empty for each test.

    Mirrors `test_compensation_api.py`'s `_tables` fixture. Truncating
    `organizations` and `shifts` with CASCADE also clears `departments`,
    `positions`, `teams`, `hr_employees`, and `work_schedules`.
    """

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
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other() -> User:
    """An authenticated user who does not own the work schedule under test."""
    return asyncio.run(_create_user(email="other@example.com", password="other-pass"))


@pytest.fixture
def other_headers(client: TestClient, other: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "other-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_employee(
    client: TestClient, headers: dict[str, str], *, user_id: str | None = None
) -> dict:
    """Creates its own HR master-data scaffolding, suffixed by a fresh id.
    Mirrors `test_compensation_api.py`'s `_create_employee` helper."""
    suffix = uuid.uuid4().hex[:8]
    organization = client.post("/organizations", json={"name": f"Acme Corp {suffix}"}).json()
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
            "name": "Backend Team",
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
    employee = response.json()
    employee["shift_id"] = shift["id"]
    return employee


_WEEKDAYS = {
    "works_monday": True,
    "works_tuesday": True,
    "works_wednesday": True,
    "works_thursday": True,
    "works_friday": True,
    "works_saturday": False,
    "works_sunday": False,
}


def _create_work_schedule(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_id: str,
    shift_id: str,
    effective_from: str = "2026-01-01",
    effective_to: str | None = None,
    corrects_id: str | None = None,
    **week_overrides: bool,
) -> dict:
    payload: dict[str, object] = {
        "employee_id": employee_id,
        "shift_id": shift_id,
        "effective_from": effective_from,
        **_WEEKDAYS,
    }
    payload.update(week_overrides)
    if effective_to is not None:
        payload["effective_to"] = effective_to
    if corrects_id is not None:
        payload["corrects_id"] = corrects_id
    response = client.post("/hr/work-schedules", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_work_schedule_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/work-schedules",
        json={
            "employee_id": str(uuid.uuid4()),
            "shift_id": str(uuid.uuid4()),
            "effective_from": "2026-01-01",
            **_WEEKDAYS,
        },
    )

    assert response.status_code == 401


def test_create_work_schedule(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    body = _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )

    assert body["employee_id"] == employee["id"]
    assert body["shift_id"] == employee["shift_id"]
    assert body["works_monday"] is True
    assert body["works_saturday"] is False
    assert body["is_active"] is True
    uuid.UUID(body["id"])


def test_create_work_schedule_rejects_missing_employee(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/work-schedules",
        json={
            "employee_id": str(uuid.uuid4()),
            "shift_id": employee["shift_id"],
            "effective_from": "2026-01-01",
            **_WEEKDAYS,
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_work_schedule_rejects_missing_shift(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/work-schedules",
        json={
            "employee_id": employee["id"],
            "shift_id": str(uuid.uuid4()),
            "effective_from": "2026-01-01",
            **_WEEKDAYS,
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_work_schedule_rejects_overlapping_period(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_work_schedule(
        client,
        user_headers,
        employee_id=employee["id"],
        shift_id=employee["shift_id"],
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )

    response = client.post(
        "/hr/work-schedules",
        json={
            "employee_id": employee["id"],
            "shift_id": employee["shift_id"],
            "effective_from": "2026-03-01",
            **_WEEKDAYS,
        },
        headers=user_headers,
    )

    assert response.status_code == 409


def test_create_work_schedule_correction(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    target = _create_work_schedule(
        client,
        user_headers,
        employee_id=employee["id"],
        shift_id=employee["shift_id"],
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )

    response = client.post(
        "/hr/work-schedules",
        json={
            "employee_id": employee["id"],
            "shift_id": employee["shift_id"],
            "effective_from": "2026-01-01",
            "effective_to": "2026-06-30",
            "corrects_id": target["id"],
            **{**_WEEKDAYS, "works_saturday": True},
        },
        headers=user_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["corrects_id"] == target["id"]
    assert body["id"] != target["id"]


def test_create_work_schedule_correction_invalid_target(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/work-schedules",
        json={
            "employee_id": employee["id"],
            "shift_id": employee["shift_id"],
            "effective_from": "2026-01-01",
            "corrects_id": str(uuid.uuid4()),
            **_WEEKDAYS,
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_work_schedule_forbidden_for_non_owner(
    client: TestClient, user_headers: dict[str, str], other: User, other_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.post(
        "/hr/work-schedules",
        json={
            "employee_id": employee["id"],
            "shift_id": employee["shift_id"],
            "effective_from": "2026-01-01",
            **_WEEKDAYS,
        },
        headers=other_headers,
    )

    assert response.status_code == 403


def test_get_work_schedule(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )

    response = client.get(f"/hr/work-schedules/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_work_schedule_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.get(f"/hr/work-schedules/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_get_work_schedule_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.get(f"/hr/work-schedules/{created['id']}", headers=other_headers)

    assert response.status_code == 403


def test_get_work_schedule_by_employee(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )

    response = client.get(f"/hr/work-schedules/by-employee/{employee['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_work_schedule_by_employee_resolves_as_of_date(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    earlier = _create_work_schedule(
        client,
        user_headers,
        employee_id=employee["id"],
        shift_id=employee["shift_id"],
        effective_from="2026-01-01",
        effective_to="2026-06-30",
    )
    response = client.post(
        "/hr/work-schedules",
        json={
            "employee_id": employee["id"],
            "shift_id": employee["shift_id"],
            "effective_from": "2026-07-01",
            **{**_WEEKDAYS, "works_saturday": True},
        },
        headers=user_headers,
    )
    assert response.status_code == 201

    response = client.get(
        f"/hr/work-schedules/by-employee/{employee['id']}",
        params={"as_of": "2026-03-01"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == earlier["id"]


def test_get_work_schedule_by_employee_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.get(f"/hr/work-schedules/by-employee/{employee['id']}", headers=other_headers)

    assert response.status_code == 403


def test_list_work_schedules_returns_only_owned(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(client, user_headers, user_id=str(other.id))
    _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )
    _create_work_schedule(
        client,
        other_headers,
        employee_id=other_employee["id"],
        shift_id=other_employee["shift_id"],
    )

    response = client.get("/hr/work-schedules", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["employee_id"] == employee["id"]


def test_update_work_schedule_only_changes_is_active(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )

    response = client.put(
        f"/hr/work-schedules/{created['id']}",
        json={"works_saturday": True, "is_active": False},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["works_saturday"] == created["works_saturday"]
    assert response.json()["is_active"] is False

    listed = client.get("/hr/work-schedules", headers=user_headers)
    assert len(listed.json()) == 1


def test_update_work_schedule_not_found(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.put(
        f"/hr/work-schedules/{uuid.uuid4()}",
        json={"is_active": False},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_work_schedule_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.put(
        f"/hr/work-schedules/{created['id']}",
        json={"is_active": False},
        headers=other_headers,
    )

    assert response.status_code == 403


def test_delete_work_schedule(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )

    response = client.delete(f"/hr/work-schedules/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/hr/work-schedules/{created['id']}", headers=user_headers).status_code == 404
    )


def test_delete_work_schedule_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_work_schedule(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.delete(f"/hr/work-schedules/{created['id']}", headers=other_headers)

    assert response.status_code == 403
