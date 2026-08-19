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

DEFAULT_DATES = {"start_date": "2026-02-10", "end_date": "2026-02-16"}


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
def manager() -> User:
    """The requester's direct manager -- the only actor the Approval
    Authorization Policy (`ADR-008`) allows to approve/reject."""
    return asyncio.run(_create_user(email="manager@example.com", password="manager-pass"))


@pytest.fixture
def manager_headers(client: TestClient, manager: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "manager@example.com", "password": "manager-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def other() -> User:
    """An authenticated user who is not the requester's manager."""
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
    manager_id: str | None = None,
) -> dict:
    """Each call creates its own HR master-data scaffolding, suffixed by a
    fresh id so multiple employees (e.g. manager + requester) can be created
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
        client, location_admin_headers, code=f"L1-{suffix}", level=int(suffix[:4], 16) + 1
    )
    employment_type = _create_employment_type(client, location_admin_headers, code=f"FT-{suffix}")
    employment_status = _create_employment_status(
        client, location_admin_headers, code=f"ACTIVE-{suffix}"
    )
    shift = _create_shift(client, location_admin_headers, code=f"DAY-{suffix}")

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
    if manager_id is not None:
        payload["manager_id"] = manager_id

    response = client.post("/hr/employees", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def _create_manager_and_requester(
    client: TestClient, headers: dict[str, str], manager_user_id: str
) -> tuple[dict, dict]:
    """A manager `HrEmployee` linked to `manager_user_id`, and a requester
    `HrEmployee` whose `manager_id` points at it -- the only relationship
    the Approval Authorization Policy (`ADR-008`) recognizes."""
    manager_employee = _create_employee(
        client,
        headers,
        employee_number="MGR-1",
        email="manager.employee@example.com",
        first_name="Grace",
        last_name="Hopper",
        full_name="Grace Hopper",
        user_id=manager_user_id,
    )
    requester_employee = _create_employee(client, headers, manager_id=manager_employee["id"])
    return manager_employee, requester_employee


def _timesheet_payload(employee_id: str, **overrides) -> dict:
    payload = {"employee_id": employee_id, **DEFAULT_DATES}
    payload.update(overrides)
    return payload


def _create_timesheet(
    client: TestClient, headers: dict[str, str], employee_id: str, **overrides
) -> dict:
    response = client.post(
        "/hr/timesheets",
        json=_timesheet_payload(employee_id, **overrides),
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_timesheet_requires_authentication(client: TestClient):
    response = client.post("/hr/timesheets", json=_timesheet_payload(str(uuid.uuid4())))

    assert response.status_code == 401


def test_list_timesheets_requires_authentication(client: TestClient):
    response = client.get("/hr/timesheets")

    assert response.status_code == 401


def test_get_timesheet_requires_authentication(client: TestClient):
    response = client.get(f"/hr/timesheets/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_timesheet_requires_authentication(client: TestClient):
    response = client.put(f"/hr/timesheets/{uuid.uuid4()}", json={"status": "approved"})

    assert response.status_code == 401


def test_delete_timesheet_requires_authentication(client: TestClient):
    response = client.delete(f"/hr/timesheets/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_timesheet(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)

    body = _create_timesheet(client, user_headers, employee["id"])

    assert body["employee_id"] == employee["id"]
    assert body["start_date"] == "2026-02-10"
    assert body["end_date"] == "2026-02-16"
    assert body["status"] == "pending"
    uuid.UUID(body["id"])


def test_create_timesheet_ignores_client_supplied_status(
    client: TestClient, user_headers: dict[str, str]
):
    """A client-supplied `status` in the create payload must not bypass
    `ApprovalService` -- `TimesheetCreate` has no `status` field, so it's
    silently dropped during validation and the new row always starts
    `pending`."""
    employee = _create_employee(client, user_headers)

    body = _create_timesheet(client, user_headers, employee["id"], status="approved")

    assert body["status"] == "pending"


def test_create_timesheet_rejects_missing_employee(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.post(
        "/hr/timesheets",
        json=_timesheet_payload(str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_timesheet_rejects_end_date_before_start_date(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)

    response = client.post(
        "/hr/timesheets",
        json=_timesheet_payload(employee["id"], start_date="2026-02-16", end_date="2026-02-10"),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_get_timesheet(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])

    response = client.get(f"/hr/timesheets/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_timesheet_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/timesheets/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_timesheets(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    _create_timesheet(client, user_headers, employee["id"])
    _create_timesheet(
        client, user_headers, employee["id"], start_date="2026-03-01", end_date="2026-03-07"
    )

    response = client.get("/hr/timesheets", headers=user_headers)

    assert response.status_code == 200
    start_dates = {item["start_date"] for item in response.json()}
    assert {"2026-02-10", "2026-03-01"}.issubset(start_dates)


def test_list_timesheets_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    for i in range(3):
        _create_timesheet(
            client,
            user_headers,
            employee["id"],
            start_date=f"2026-02-{10 + i:02d}",
            end_date=f"2026-02-{16 + i:02d}",
        )

    response = client.get("/hr/timesheets/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_timesheets_paginated_custom_offset(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    for i in range(5):
        _create_timesheet(
            client,
            user_headers,
            employee["id"],
            start_date=f"2026-02-{10 + i:02d}",
            end_date=f"2026-02-{16 + i:02d}",
        )

    response = client.get("/hr/timesheets/paginated", headers=user_headers, params={"offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_timesheets_paginated_filter_by_status(
    client: TestClient,
    user_headers: dict[str, str],
    manager: User,
    manager_headers: dict[str, str],
):
    """The `approved` row must come from the real approval flow, not a
    create-time `status` override -- `TimesheetCreate` has no `status`
    field, so it can no longer be set at creation."""
    _, requester = _create_manager_and_requester(client, user_headers, str(manager.id))
    approved = _create_timesheet(client, user_headers, requester["id"])
    client.post(f"/hr/timesheets/{approved['id']}/approve", headers=manager_headers)
    _create_timesheet(
        client,
        user_headers,
        requester["id"],
        start_date="2026-03-01",
        end_date="2026-03-07",
    )

    response = client.get(
        "/hr/timesheets/paginated", headers=user_headers, params={"status": "approved"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "approved"


def test_list_timesheets_paginated_filter_by_employee_id(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])

    response = client.get(
        "/hr/timesheets/paginated",
        headers=user_headers,
        params={"employee_id": employee["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_list_timesheets_paginated_filter_by_start_date(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])
    _create_timesheet(
        client, user_headers, employee["id"], start_date="2026-03-01", end_date="2026-03-07"
    )

    response = client.get(
        "/hr/timesheets/paginated",
        headers=user_headers,
        params={"start_date": "2026-02-10"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_list_timesheets_paginated_filter_by_end_date(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])
    _create_timesheet(
        client, user_headers, employee["id"], start_date="2026-03-01", end_date="2026-03-07"
    )

    response = client.get(
        "/hr/timesheets/paginated",
        headers=user_headers,
        params={"end_date": "2026-02-16"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_update_timesheet(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])

    response = client.put(
        f"/hr/timesheets/{created['id']}",
        json={"status": "approved"},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_update_timesheet_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/hr/timesheets/{uuid.uuid4()}",
        json={"status": "approved"},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_timesheet_rejects_missing_employee(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])

    response = client.put(
        f"/hr/timesheets/{created['id']}",
        json={"employee_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_timesheet_rejects_end_date_before_start_date(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])

    response = client.put(
        f"/hr/timesheets/{created['id']}",
        json={"end_date": "2026-01-01"},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_timesheet_rejected_when_approved(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])
    client.put(f"/hr/timesheets/{created['id']}", json={"status": "approved"}, headers=user_headers)

    response = client.put(
        f"/hr/timesheets/{created['id']}",
        json={"start_date": "2026-02-11"},
        headers=user_headers,
    )

    assert response.status_code == 409


def test_update_timesheet_rejected_when_rejected(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])
    client.put(f"/hr/timesheets/{created['id']}", json={"status": "rejected"}, headers=user_headers)

    response = client.put(
        f"/hr/timesheets/{created['id']}",
        json={"start_date": "2026-02-11"},
        headers=user_headers,
    )

    assert response.status_code == 409


def test_delete_pending_timesheet_succeeds(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])

    response = client.delete(f"/hr/timesheets/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/hr/timesheets/{created['id']}", headers=user_headers).status_code == 404


def test_delete_timesheet_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/hr/timesheets/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_delete_approved_timesheet_rejected(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])
    client.put(f"/hr/timesheets/{created['id']}", json={"status": "approved"}, headers=user_headers)

    response = client.delete(f"/hr/timesheets/{created['id']}", headers=user_headers)

    assert response.status_code == 409
    assert client.get(f"/hr/timesheets/{created['id']}", headers=user_headers).status_code == 200


def test_delete_rejected_timesheet_rejected(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    created = _create_timesheet(client, user_headers, employee["id"])
    client.put(f"/hr/timesheets/{created['id']}", json={"status": "rejected"}, headers=user_headers)

    response = client.delete(f"/hr/timesheets/{created['id']}", headers=user_headers)

    assert response.status_code == 409
    assert client.get(f"/hr/timesheets/{created['id']}", headers=user_headers).status_code == 200


def test_approve_timesheet_requires_authentication(client: TestClient):
    response = client.post(f"/hr/timesheets/{uuid.uuid4()}/approve")

    assert response.status_code == 401


def test_reject_timesheet_requires_authentication(client: TestClient):
    response = client.post(f"/hr/timesheets/{uuid.uuid4()}/reject", json={"reason": "No"})

    assert response.status_code == 401


def test_approve_timesheet_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(f"/hr/timesheets/{uuid.uuid4()}/approve", headers=user_headers)

    assert response.status_code == 404


def test_reject_timesheet_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        f"/hr/timesheets/{uuid.uuid4()}/reject", json={"reason": "No"}, headers=user_headers
    )

    assert response.status_code == 404


def test_approve_timesheet(
    client: TestClient,
    user_headers: dict[str, str],
    manager: User,
    manager_headers: dict[str, str],
):
    _, requester = _create_manager_and_requester(client, user_headers, str(manager.id))
    created = _create_timesheet(client, user_headers, requester["id"])

    response = client.post(f"/hr/timesheets/{created['id']}/approve", headers=manager_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["approved_by"] == str(manager.id)
    assert body["approved_at"] is not None
    assert body["rejection_reason"] is None


def test_reject_timesheet(
    client: TestClient,
    user_headers: dict[str, str],
    manager: User,
    manager_headers: dict[str, str],
):
    _, requester = _create_manager_and_requester(client, user_headers, str(manager.id))
    created = _create_timesheet(client, user_headers, requester["id"])

    response = client.post(
        f"/hr/timesheets/{created['id']}/reject",
        json={"reason": "Insufficient coverage"},
        headers=manager_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["approved_by"] == str(manager.id)
    assert body["approved_at"] is not None
    assert body["rejection_reason"] == "Insufficient coverage"


def test_approve_timesheet_rejects_non_pending(
    client: TestClient,
    user_headers: dict[str, str],
    manager: User,
    manager_headers: dict[str, str],
):
    _, requester = _create_manager_and_requester(client, user_headers, str(manager.id))
    created = _create_timesheet(client, user_headers, requester["id"])
    client.post(f"/hr/timesheets/{created['id']}/approve", headers=manager_headers)

    response = client.post(f"/hr/timesheets/{created['id']}/approve", headers=manager_headers)

    assert response.status_code == 409


def test_reject_timesheet_rejects_non_pending(
    client: TestClient,
    user_headers: dict[str, str],
    manager: User,
    manager_headers: dict[str, str],
):
    _, requester = _create_manager_and_requester(client, user_headers, str(manager.id))
    created = _create_timesheet(client, user_headers, requester["id"])
    client.post(
        f"/hr/timesheets/{created['id']}/reject",
        json={"reason": "No"},
        headers=manager_headers,
    )

    response = client.post(
        f"/hr/timesheets/{created['id']}/reject",
        json={"reason": "No"},
        headers=manager_headers,
    )

    assert response.status_code == 409


def test_approve_timesheet_forbidden_for_non_manager(
    client: TestClient,
    user_headers: dict[str, str],
    manager: User,
    other: User,
    other_headers: dict[str, str],
):
    _, requester = _create_manager_and_requester(client, user_headers, str(manager.id))
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
    created = _create_timesheet(client, user_headers, requester["id"])

    response = client.post(f"/hr/timesheets/{created['id']}/approve", headers=other_headers)

    assert response.status_code == 403
    assert (
        client.get(f"/hr/timesheets/{created['id']}", headers=user_headers).json()["status"]
        == "pending"
    )


def test_reject_timesheet_forbidden_for_non_manager(
    client: TestClient,
    user_headers: dict[str, str],
    manager: User,
    other: User,
    other_headers: dict[str, str],
):
    _, requester = _create_manager_and_requester(client, user_headers, str(manager.id))
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
    created = _create_timesheet(client, user_headers, requester["id"])

    response = client.post(
        f"/hr/timesheets/{created['id']}/reject",
        json={"reason": "No"},
        headers=other_headers,
    )

    assert response.status_code == 403
    assert (
        client.get(f"/hr/timesheets/{created['id']}", headers=user_headers).json()["status"]
        == "pending"
    )
