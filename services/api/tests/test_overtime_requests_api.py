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

DEFAULT_TIMES = {
    "overtime_date": "2026-02-10",
    "start_time": "18:00:00",
    "end_time": "20:00:00",
}


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures all tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables. Truncating `organizations` and `shifts` with CASCADE also clears
    `departments`, `positions`, `teams`, `hr_employees`, and `overtime_requests`.
    `locations`, `location_types`, `job_grades`, `employment_types`, and
    `employment_statuses` don't depend on `organizations`, so they're
    truncated explicitly.
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
    return response.json()


def _overtime_request_payload(employee_id: str, **overrides) -> dict:
    payload = {"employee_id": employee_id, **DEFAULT_TIMES}
    payload.update(overrides)
    return payload


def _create_overtime_request(
    client: TestClient, headers: dict[str, str], employee_id: str, **overrides
) -> dict:
    response = client.post(
        "/hr/overtime-requests",
        json=_overtime_request_payload(employee_id, **overrides),
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_overtime_request_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/overtime-requests", json=_overtime_request_payload(str(uuid.uuid4()))
    )

    assert response.status_code == 401


def test_list_overtime_requests_requires_authentication(client: TestClient):
    response = client.get("/hr/overtime-requests")

    assert response.status_code == 401


def test_get_overtime_request_requires_authentication(client: TestClient):
    response = client.get(f"/hr/overtime-requests/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_overtime_request_requires_authentication(client: TestClient):
    response = client.put(f"/hr/overtime-requests/{uuid.uuid4()}", json={"status": "approved"})

    assert response.status_code == 401


def test_delete_overtime_request_requires_authentication(client: TestClient):
    response = client.delete(f"/hr/overtime-requests/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_overtime_request(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)

    body = _create_overtime_request(client, user_headers, employee["id"])

    assert body["employee_id"] == employee["id"]
    assert body["overtime_date"] == "2026-02-10"
    assert body["start_time"] == "18:00:00"
    assert body["end_time"] == "20:00:00"
    assert body["status"] == "pending"
    assert body["reason"] is None
    uuid.UUID(body["id"])


def test_create_overtime_request_rejects_missing_employee(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.post(
        "/hr/overtime-requests",
        json=_overtime_request_payload(str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_overtime_request_rejects_end_time_before_start_time(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)

    response = client.post(
        "/hr/overtime-requests",
        json=_overtime_request_payload(
            employee["id"], start_time="20:00:00", end_time="18:00:00"
        ),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_get_overtime_request(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_overtime_request(client, user_headers, employee["id"])

    response = client.get(f"/hr/overtime-requests/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_overtime_request_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/overtime-requests/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_overtime_requests(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    _create_overtime_request(client, user_headers, employee["id"])
    _create_overtime_request(client, user_headers, employee["id"], overtime_date="2026-03-01")

    response = client.get("/hr/overtime-requests", headers=user_headers)

    assert response.status_code == 200
    overtime_dates = {item["overtime_date"] for item in response.json()}
    assert {"2026-02-10", "2026-03-01"}.issubset(overtime_dates)


def test_list_overtime_requests_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    for i in range(3):
        _create_overtime_request(
            client, user_headers, employee["id"], overtime_date=f"2026-02-{10 + i:02d}"
        )

    response = client.get("/hr/overtime-requests/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_overtime_requests_paginated_custom_offset(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    for i in range(5):
        _create_overtime_request(
            client, user_headers, employee["id"], overtime_date=f"2026-02-{10 + i:02d}"
        )

    response = client.get(
        "/hr/overtime-requests/paginated", headers=user_headers, params={"offset": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_overtime_requests_paginated_search_by_reason(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_overtime_request(
        client, user_headers, employee["id"], reason="Quarter-end close"
    )
    _create_overtime_request(
        client,
        user_headers,
        employee["id"],
        overtime_date="2026-03-01",
        reason="Production incident",
    )

    response = client.get(
        "/hr/overtime-requests/paginated", headers=user_headers, params={"q": "close"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["reason"] == "Quarter-end close"


def test_list_overtime_requests_paginated_filter_by_status(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    _create_overtime_request(client, user_headers, employee["id"], status="approved")
    _create_overtime_request(
        client, user_headers, employee["id"], overtime_date="2026-03-01", status="pending"
    )

    response = client.get(
        "/hr/overtime-requests/paginated", headers=user_headers, params={"status": "approved"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "approved"


def test_list_overtime_requests_paginated_filter_by_employee_id(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    created = _create_overtime_request(client, user_headers, employee["id"])

    response = client.get(
        "/hr/overtime-requests/paginated",
        headers=user_headers,
        params={"employee_id": employee["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_update_overtime_request(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_overtime_request(client, user_headers, employee["id"])

    response = client.put(
        f"/hr/overtime-requests/{created['id']}",
        json={"status": "approved"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_update_overtime_request_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/hr/overtime-requests/{uuid.uuid4()}",
        json={"status": "approved"},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_overtime_request_rejects_missing_employee(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    created = _create_overtime_request(client, user_headers, employee["id"])

    response = client.put(
        f"/hr/overtime-requests/{created['id']}",
        json={"employee_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_overtime_request_rejects_end_time_before_start_time(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    created = _create_overtime_request(client, user_headers, employee["id"])

    response = client.put(
        f"/hr/overtime-requests/{created['id']}",
        json={"end_time": "17:00:00"},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_delete_overtime_request(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_overtime_request(client, user_headers, employee["id"])

    response = client.delete(f"/hr/overtime-requests/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/hr/overtime-requests/{created['id']}", headers=user_headers).status_code
        == 404
    )


def test_delete_overtime_request_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/hr/overtime-requests/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_approve_overtime_request_requires_authentication(client: TestClient):
    response = client.post(f"/hr/overtime-requests/{uuid.uuid4()}/approve")

    assert response.status_code == 401


def test_reject_overtime_request_requires_authentication(client: TestClient):
    response = client.post(
        f"/hr/overtime-requests/{uuid.uuid4()}/reject", json={"reason": "No"}
    )

    assert response.status_code == 401


def test_approve_overtime_request_not_implemented(
    client: TestClient, user_headers: dict[str, str]
):
    """Approval orchestration is intentionally deferred (no shared architectural
    decision yet, per docs/architecture/APPROVAL_WORKFLOW_DESIGN.md §10) -- the
    endpoint exists but always responds 501, regardless of whether the id exists."""
    response = client.post(
        f"/hr/overtime-requests/{uuid.uuid4()}/approve", headers=user_headers
    )

    assert response.status_code == 501


def test_reject_overtime_request_not_implemented(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.post(
        f"/hr/overtime-requests/{uuid.uuid4()}/reject",
        json={"reason": "No"},
        headers=user_headers,
    )

    assert response.status_code == 501
