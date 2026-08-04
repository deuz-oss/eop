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

TARGET_DATE = "2026-03-02"


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures all tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables. Truncating `organizations` and `shifts` with CASCADE also clears
    `departments`, `positions`, `teams`, `hr_employees`, `attendance_events`,
    and `leave_requests`. `locations`, `location_types`, `job_grades`,
    `employment_types`, and `employment_statuses` don't depend on
    `organizations`, so they're truncated explicitly. `holidays` has no FK
    into any of these and is truncated on its own.
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
                    "job_grades, employment_types, employment_statuses, shifts, users, "
                    "holidays CASCADE"
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


def _create_organization(
    client: TestClient, headers: dict[str, str], *, name: str = "Acme Corp"
) -> dict:
    response = client.post("/organizations", json={"name": name})
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


def _create_employee(client: TestClient, headers: dict[str, str]) -> dict:
    organization = _create_organization(client, headers)
    department = _create_department(client, headers, organization_id=organization["id"])
    position = _create_position(
        client, headers, organization_id=organization["id"], department_id=department["id"]
    )
    team = _create_team(
        client, headers, organization_id=organization["id"], department_id=department["id"]
    )
    location_type = _create_location_type(client, headers)
    location = _create_location(client, headers, location_type_id=location_type["id"])
    job_grade = _create_job_grade(client, headers)
    employment_type = _create_employment_type(client, headers)
    employment_status = _create_employment_status(client, headers)
    shift = _create_shift(client, headers)

    response = client.post(
        "/hr/employees",
        json={
            "employee_number": "EMP-1",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
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
    employee = response.json()
    employee["shift_id"] = shift["id"]
    return employee


def _create_attendance_event(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_id: str,
    shift_id: str,
    event_time: str = "2026-03-02T09:00:00Z",
) -> dict:
    response = client.post(
        "/hr/attendance-events",
        json={
            "employee_id": employee_id,
            "shift_id": shift_id,
            "event_type": "CLOCK_IN",
            "event_time": event_time,
            "source": "SYSTEM",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _create_approved_leave_request(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_id: str,
    start_date: str = "2026-03-01",
    end_date: str = "2026-03-03",
) -> dict:
    response = client.post(
        "/hr/leave-requests",
        json={"employee_id": employee_id, "start_date": start_date, "end_date": end_date},
        headers=headers,
    )
    assert response.status_code == 201
    leave_request = response.json()

    response = client.put(
        f"/hr/leave-requests/{leave_request['id']}",
        json={"status": "approved"},
        headers=headers,
    )
    assert response.status_code == 200
    return response.json()


def _create_holiday(
    client: TestClient,
    headers: dict[str, str],
    *,
    holiday_date: str = TARGET_DATE,
    code: str = "HOL-1",
    name: str = "Founders Day",
) -> dict:
    response = client.post(
        "/hr/holidays",
        json={"code": code, "name": name, "holiday_date": holiday_date},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_get_reconciliation_requires_authentication(client: TestClient):
    response = client.get(
        "/hr/reconciliation", params={"employee_id": str(uuid.uuid4()), "date": TARGET_DATE}
    )

    assert response.status_code == 401


def test_get_reconciliation_employee_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(
        "/hr/reconciliation",
        params={"employee_id": str(uuid.uuid4()), "date": TARGET_DATE},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_get_reconciliation_absent_when_no_facts(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)

    response = client.get(
        "/hr/reconciliation",
        params={"employee_id": employee["id"], "date": TARGET_DATE},
        headers=user_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["employee_id"] == employee["id"]
    assert body["date"] == TARGET_DATE
    assert body["status"] == "absent"


def test_get_reconciliation_present_when_attendance_event_exists(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_attendance_event(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )

    response = client.get(
        "/hr/reconciliation",
        params={"employee_id": employee["id"], "date": TARGET_DATE},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "present"


def test_get_reconciliation_leave_when_approved_leave_request_covers_date(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_approved_leave_request(client, user_headers, employee_id=employee["id"])

    response = client.get(
        "/hr/reconciliation",
        params={"employee_id": employee["id"], "date": TARGET_DATE},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "leave"


def test_get_reconciliation_holiday_when_date_is_holiday(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_holiday(client, user_headers)

    response = client.get(
        "/hr/reconciliation",
        params={"employee_id": employee["id"], "date": TARGET_DATE},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "holiday"


def test_get_reconciliation_precedence_holiday_beats_leave_and_attendance(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_holiday(client, user_headers)
    _create_approved_leave_request(client, user_headers, employee_id=employee["id"])
    _create_attendance_event(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )

    response = client.get(
        "/hr/reconciliation",
        params={"employee_id": employee["id"], "date": TARGET_DATE},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "holiday"


def test_get_reconciliation_precedence_leave_beats_attendance(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_approved_leave_request(client, user_headers, employee_id=employee["id"])
    _create_attendance_event(
        client, user_headers, employee_id=employee["id"], shift_id=employee["shift_id"]
    )

    response = client.get(
        "/hr/reconciliation",
        params={"employee_id": employee["id"], "date": TARGET_DATE},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "leave"
