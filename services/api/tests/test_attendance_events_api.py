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

DEFAULT_EVENT_TIME = "2026-01-05T09:00:00Z"


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
    """An authenticated user who does not own the attendance event under test."""
    return asyncio.run(_create_user(email="other@example.com", password="other-pass"))


@pytest.fixture
def other_headers(client: TestClient, other: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "other-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_organization(
    client: TestClient, headers: dict[str, str], *, name: str = "Acme Corp"
) -> dict:
    response = client.post("/organizations", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()


def _create_department(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Engineering",
    code: str = "ENG",
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
    code: str = "ENG-1",
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
    code: str = "BACKEND",
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
    client: TestClient, headers: dict[str, str], *, name: str = "Office", code: str = "OFFICE"
) -> dict:
    response = client.post("/location-types", json={"name": name, "code": code}, headers=headers)
    assert response.status_code == 201
    return response.json()


def _create_location(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "HQ",
    code: str = "HQ",
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
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Engineer I",
    code: str = "L1",
    level: int = 1,
) -> dict:
    response = client.post(
        "/hr/job-grades", json={"name": name, "code": code, "level": level}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_employment_type(
    client: TestClient, headers: dict[str, str], *, name: str = "Full-Time", code: str = "FT"
) -> dict:
    response = client.post(
        "/hr/employment-types", json={"name": name, "code": code}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_employment_status(
    client: TestClient, headers: dict[str, str], *, name: str = "Active", code: str = "ACTIVE"
) -> dict:
    response = client.post(
        "/hr/employment-statuses", json={"name": name, "code": code}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_shift(
    client: TestClient, headers: dict[str, str], *, name: str = "Day Shift", code: str = "DAY"
) -> dict:
    response = client.post(
        "/hr/shifts",
        json={"code": code, "name": name, "start_time": "09:00:00", "end_time": "17:00:00"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_employee(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_number: str = "EMP-1",
    email: str = "ada@example.com",
    first_name: str = "Ada",
    last_name: str = "Lovelace",
    full_name: str = "Ada Lovelace",
    user_id: str | None = None,
) -> dict:
    """Each call creates its own HR master-data scaffolding, suffixed by a
    fresh id so multiple employees (e.g. owner + non-owner) can be created
    within the same test without violating the `code`/`name` uniqueness
    constraints on organizations/departments/.../shifts."""
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
        client, headers, code=f"L1-{suffix}", level=int(suffix[:4], 16) + 1
    )
    employment_type = _create_employment_type(client, headers, code=f"FT-{suffix}")
    employment_status = _create_employment_status(client, headers, code=f"ACTIVE-{suffix}")
    shift = _create_shift(client, headers, code=f"DAY-{suffix}")

    payload: dict = {
        "employee_number": employee_number,
        "first_name": first_name,
        "last_name": last_name,
        "full_name": full_name,
        "email": email,
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


def _attendance_event_payload(employee_id: str, shift_id: str, **overrides) -> dict:
    payload = {
        "employee_id": employee_id,
        "shift_id": shift_id,
        "event_type": "CLOCK_IN",
        "event_time": DEFAULT_EVENT_TIME,
        "source": "SYSTEM",
    }
    payload.update(overrides)
    return payload


def _create_attendance_event(
    client: TestClient, headers: dict[str, str], employee_id: str, shift_id: str, **overrides
) -> dict:
    response = client.post(
        "/hr/attendance-events",
        json=_attendance_event_payload(employee_id, shift_id, **overrides),
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_attendance_event_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/attendance-events",
        json=_attendance_event_payload(str(uuid.uuid4()), str(uuid.uuid4())),
    )

    assert response.status_code == 401


def test_list_attendance_events_requires_authentication(client: TestClient):
    response = client.get("/hr/attendance-events")

    assert response.status_code == 401


def test_get_attendance_event_requires_authentication(client: TestClient):
    response = client.get(f"/hr/attendance-events/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_attendance_event_requires_authentication(client: TestClient):
    response = client.put(f"/hr/attendance-events/{uuid.uuid4()}", json={"remarks": "Corrected"})

    assert response.status_code == 401


def test_delete_attendance_event_requires_authentication(client: TestClient):
    response = client.delete(f"/hr/attendance-events/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_attendance_event(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    body = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])

    assert body["employee_id"] == employee["id"]
    assert body["shift_id"] == employee["shift_id"]
    assert body["event_type"] == "CLOCK_IN"
    assert body["source"] == "SYSTEM"
    assert body["remarks"] is None
    uuid.UUID(body["id"])


def test_create_attendance_event_rejects_missing_employee(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/attendance-events",
        json=_attendance_event_payload(str(uuid.uuid4()), employee["shift_id"]),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_attendance_event_rejects_missing_shift(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/attendance-events",
        json=_attendance_event_payload(employee["id"], str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_attendance_event_rejects_invalid_event_type(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/attendance-events",
        json=_attendance_event_payload(employee["id"], employee["shift_id"], event_type="INVALID"),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_attendance_event_rejects_invalid_source(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/hr/attendance-events",
        json=_attendance_event_payload(employee["id"], employee["shift_id"], source="MOBILE"),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_attendance_event_forbidden_for_non_owner(
    client: TestClient, user_headers: dict[str, str], other: User, other_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )

    response = client.post(
        "/hr/attendance-events",
        json=_attendance_event_payload(employee["id"], employee["shift_id"]),
        headers=other_headers,
    )

    assert response.status_code == 403


def test_get_attendance_event(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])

    response = client.get(f"/hr/attendance-events/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_attendance_event_not_found(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.get(f"/hr/attendance-events/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_get_attendance_event_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])
    _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )

    response = client.get(f"/hr/attendance-events/{created['id']}", headers=other_headers)

    assert response.status_code == 403


def test_list_attendance_events(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])
    _create_attendance_event(
        client,
        user_headers,
        employee["id"],
        employee["shift_id"],
        event_type="CLOCK_OUT",
        event_time="2026-01-05T17:00:00Z",
    )

    response = client.get("/hr/attendance-events", headers=user_headers)

    assert response.status_code == 200
    event_types = {item["event_type"] for item in response.json()}
    assert {"CLOCK_IN", "CLOCK_OUT"}.issubset(event_types)


def test_list_attendance_events_returns_only_owned(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )
    _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])
    _create_attendance_event(
        client, other_headers, other_employee["id"], other_employee["shift_id"]
    )

    response = client.get("/hr/attendance-events", headers=user_headers)

    assert response.status_code == 200
    assert {item["employee_id"] for item in response.json()} == {employee["id"]}


def test_list_attendance_events_paginated_default_pagination(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    for i in range(3):
        _create_attendance_event(
            client,
            user_headers,
            employee["id"],
            employee["shift_id"],
            event_time=f"2026-01-05T09:0{i}:00Z",
        )

    response = client.get("/hr/attendance-events/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_attendance_events_paginated_custom_offset(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    for i in range(5):
        _create_attendance_event(
            client,
            user_headers,
            employee["id"],
            employee["shift_id"],
            event_time=f"2026-01-05T09:0{i}:00Z",
        )

    response = client.get(
        "/hr/attendance-events/paginated", headers=user_headers, params={"offset": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_attendance_events_paginated_search_by_remarks(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_attendance_event(
        client,
        user_headers,
        employee["id"],
        employee["shift_id"],
        remarks="Late due to traffic",
    )
    _create_attendance_event(
        client,
        user_headers,
        employee["id"],
        employee["shift_id"],
        event_type="CLOCK_OUT",
        event_time="2026-01-05T17:00:00Z",
        remarks="On time",
    )

    response = client.get(
        "/hr/attendance-events/paginated", headers=user_headers, params={"q": "traffic"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["remarks"] == "Late due to traffic"


def test_list_attendance_events_paginated_filter_by_event_type(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])
    _create_attendance_event(
        client,
        user_headers,
        employee["id"],
        employee["shift_id"],
        event_type="CLOCK_OUT",
        event_time="2026-01-05T17:00:00Z",
    )

    response = client.get(
        "/hr/attendance-events/paginated",
        headers=user_headers,
        params={"event_type": "CLOCK_OUT"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["event_type"] == "CLOCK_OUT"


def test_list_attendance_events_paginated_filter_by_employee_id_is_ignored(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    """A caller cannot widen scope by passing a different `employee_id` filter --
    the response is still scoped to the caller's own employee (Owner Only)."""
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])
    _create_attendance_event(
        client, other_headers, other_employee["id"], other_employee["shift_id"]
    )

    response = client.get(
        "/hr/attendance-events/paginated",
        headers=user_headers,
        params={"employee_id": other_employee["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_update_attendance_event(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])

    response = client.put(
        f"/hr/attendance-events/{created['id']}",
        json={"remarks": "Corrected"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["remarks"] == "Corrected"


def test_update_attendance_event_not_found(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.put(
        f"/hr/attendance-events/{uuid.uuid4()}",
        json={"remarks": "Corrected"},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_attendance_event_rejects_missing_employee(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])

    response = client.put(
        f"/hr/attendance-events/{created['id']}",
        json={"employee_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_attendance_event_rejects_missing_shift(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])

    response = client.put(
        f"/hr/attendance-events/{created['id']}",
        json={"shift_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_attendance_event_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])
    _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )

    response = client.put(
        f"/hr/attendance-events/{created['id']}",
        json={"remarks": "Corrected"},
        headers=other_headers,
    )

    assert response.status_code == 403


def test_delete_attendance_event(client: TestClient, user: User, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])

    response = client.delete(f"/hr/attendance-events/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/hr/attendance-events/{created['id']}", headers=user_headers).status_code
        == 404
    )


def test_delete_attendance_event_not_found(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.delete(f"/hr/attendance-events/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_delete_attendance_event_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    created = _create_attendance_event(client, user_headers, employee["id"], employee["shift_id"])
    _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )

    response = client.delete(f"/hr/attendance-events/{created['id']}", headers=other_headers)

    assert response.status_code == 403
