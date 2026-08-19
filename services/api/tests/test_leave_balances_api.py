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

# LeaveBalance Authorization: reads remain open to any authenticated user;
# create/update/delete are Role Based (`RequireRole("admin")`), per CTO
# decision L2. Reuses `_location_admin_headers` -- the same "admin" role
# already seeded for the Location/LocationType master-data bootstrap below --
# for LeaveBalance's own write authorization, rather than introducing a
# second RBAC helper.

DEFAULT_BALANCE = {
    "period_year": 2026,
    "allocated_days": 12,
}


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
    """A throwaway admin session, seeded with the "admin" role. Originally
    used only for the Location/LocationType master-data bootstrap below;
    also reused directly for JobGrade/EmploymentType/EmploymentStatus/Shift
    bootstrap and for LeaveBalance's own write authorization (CTO decision
    L2, `RequireRole("admin")`) -- the same role, the same mechanism, no
    second RBAC helper introduced. The employee/user actually under test
    keeps its own identity."""
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


def _create_employee(client: TestClient, headers: dict[str, str]) -> dict:
    organization = _create_organization(client, headers)
    department = _create_department(client, headers, organization_id=organization["id"])
    position = _create_position(
        client, headers, organization_id=organization["id"], department_id=department["id"]
    )
    team = _create_team(
        client, headers, organization_id=organization["id"], department_id=department["id"]
    )
    # All master-data bootstrap (Location/LocationType/JobGrade/
    # EmploymentType/EmploymentStatus/Shift) now requires the "admin" role
    # (CTO decision H2) -- one shared admin session covers all of it.
    master_data_admin_headers = _location_admin_headers(client)
    location_type = _create_location_type(client, master_data_admin_headers)
    location = _create_location(
        client, master_data_admin_headers, location_type_id=location_type["id"]
    )
    job_grade = _create_job_grade(client, master_data_admin_headers)
    employment_type = _create_employment_type(client, master_data_admin_headers)
    employment_status = _create_employment_status(client, master_data_admin_headers)
    shift = _create_shift(client, master_data_admin_headers)

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


def _leave_balance_payload(employee_id: str, **overrides) -> dict:
    payload = {"employee_id": employee_id, **DEFAULT_BALANCE}
    payload.update(overrides)
    return payload


def _create_leave_balance(
    client: TestClient, headers: dict[str, str], employee_id: str, **overrides
) -> dict:
    response = client.post(
        "/hr/leave-balances",
        json=_leave_balance_payload(employee_id, **overrides),
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_leave_balance_requires_authentication(client: TestClient):
    response = client.post("/hr/leave-balances", json=_leave_balance_payload(str(uuid.uuid4())))

    assert response.status_code == 401


def test_list_leave_balances_requires_authentication(client: TestClient):
    response = client.get("/hr/leave-balances")

    assert response.status_code == 401


def test_get_leave_balance_requires_authentication(client: TestClient):
    response = client.get(f"/hr/leave-balances/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_leave_balance_requires_authentication(client: TestClient):
    response = client.put(f"/hr/leave-balances/{uuid.uuid4()}", json={"allocated_days": 3})

    assert response.status_code == 401


def test_delete_leave_balance_requires_authentication(client: TestClient):
    response = client.delete(f"/hr/leave-balances/{uuid.uuid4()}")

    assert response.status_code == 401


# --- authorization: reads open to any authenticated user, writes admin-only ---


def test_list_leave_balances_allows_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.get("/hr/leave-balances", headers=user_headers)

    assert response.status_code == 200


def test_get_leave_balance_allows_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/leave-balances/{uuid.uuid4()}", headers=user_headers)

    # 404 (not 403) proves the request reached the service layer -- the
    # non-admin caller was not rejected by authorization.
    assert response.status_code == 404


def test_list_leave_balances_allows_admin(client: TestClient):
    admin_headers = _location_admin_headers(client)

    response = client.get("/hr/leave-balances", headers=admin_headers)

    assert response.status_code == 200


def test_create_leave_balance_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.post(
        "/hr/leave-balances",
        json=_leave_balance_payload(str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 403


def test_update_leave_balance_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/hr/leave-balances/{uuid.uuid4()}", json={"allocated_days": 3}, headers=user_headers
    )

    assert response.status_code == 403


def test_delete_leave_balance_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/hr/leave-balances/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 403


# --- create ---------------------------------------------------------------


def test_create_leave_balance(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)

    body = _create_leave_balance(client, admin_headers, employee["id"])

    assert body["employee_id"] == employee["id"]
    assert body["period_year"] == 2026
    assert body["allocated_days"] == 12
    assert body["used_days"] == 0
    assert body["remaining_days"] == 12
    uuid.UUID(body["id"])


def test_create_leave_balance_ignores_client_supplied_used_days(
    client: TestClient, user_headers: dict[str, str]
):
    """A client-supplied `used_days`/`remaining_days` in the create payload
    must not bypass `ApprovalService._sync_leave_balance` -- `LeaveBalanceCreate`
    has neither field, so both are silently dropped and the new row always
    starts `used_days=0`, `remaining_days=allocated_days`."""
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)

    body = _create_leave_balance(
        client, admin_headers, employee["id"], used_days=99, remaining_days=1
    )

    assert body["used_days"] == 0
    assert body["remaining_days"] == 12


def test_create_leave_balance_rejects_missing_employee(client: TestClient):
    admin_headers = _location_admin_headers(client)

    response = client.post(
        "/hr/leave-balances",
        json=_leave_balance_payload(str(uuid.uuid4())),
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_create_leave_balance_rejects_negative_allocated_days(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)

    response = client.post(
        "/hr/leave-balances",
        json=_leave_balance_payload(employee["id"], allocated_days=-1),
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_get_leave_balance(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    created = _create_leave_balance(client, admin_headers, employee["id"])

    response = client.get(f"/hr/leave-balances/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_leave_balance_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/leave-balances/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_leave_balances(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    _create_leave_balance(client, admin_headers, employee["id"], period_year=2025)
    _create_leave_balance(client, admin_headers, employee["id"], period_year=2026)

    response = client.get("/hr/leave-balances", headers=user_headers)

    assert response.status_code == 200
    period_years = {item["period_year"] for item in response.json()}
    assert {2025, 2026}.issubset(period_years)


def test_list_leave_balances_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    for i in range(3):
        _create_leave_balance(client, admin_headers, employee["id"], period_year=2022 + i)

    response = client.get("/hr/leave-balances/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_leave_balances_paginated_custom_offset(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    for i in range(5):
        _create_leave_balance(client, admin_headers, employee["id"], period_year=2022 + i)

    response = client.get(
        "/hr/leave-balances/paginated", headers=user_headers, params={"offset": 2}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_leave_balances_paginated_filter_by_employee_id(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    created = _create_leave_balance(client, admin_headers, employee["id"])

    response = client.get(
        "/hr/leave-balances/paginated",
        headers=user_headers,
        params={"employee_id": employee["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_list_leave_balances_paginated_filter_by_period_year(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    created = _create_leave_balance(client, admin_headers, employee["id"], period_year=2026)
    _create_leave_balance(client, admin_headers, employee["id"], period_year=2027)

    response = client.get(
        "/hr/leave-balances/paginated", headers=user_headers, params={"period_year": 2026}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_update_leave_balance(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    created = _create_leave_balance(client, admin_headers, employee["id"])

    response = client.put(
        f"/hr/leave-balances/{created['id']}",
        json={"allocated_days": 20},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["allocated_days"] == 20
    assert body["used_days"] == 0
    assert body["remaining_days"] == 20


def test_update_leave_balance_ignores_client_supplied_used_days(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    created = _create_leave_balance(client, admin_headers, employee["id"])

    response = client.put(
        f"/hr/leave-balances/{created['id']}",
        json={"used_days": 99, "remaining_days": 1},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["used_days"] == 0
    assert body["remaining_days"] == 12


def test_update_leave_balance_not_found(client: TestClient):
    admin_headers = _location_admin_headers(client)

    response = client.put(
        f"/hr/leave-balances/{uuid.uuid4()}",
        json={"allocated_days": 5},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_leave_balance_rejects_missing_employee(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    created = _create_leave_balance(client, admin_headers, employee["id"])

    response = client.put(
        f"/hr/leave-balances/{created['id']}",
        json={"employee_id": str(uuid.uuid4())},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_leave_balance_rejects_negative_allocated_days(
    client: TestClient, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    created = _create_leave_balance(client, admin_headers, employee["id"])

    response = client.put(
        f"/hr/leave-balances/{created['id']}",
        json={"allocated_days": -1},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_delete_leave_balance(client: TestClient, user_headers: dict[str, str]):
    employee = _create_employee(client, user_headers)
    admin_headers = _location_admin_headers(client)
    created = _create_leave_balance(client, admin_headers, employee["id"])

    response = client.delete(f"/hr/leave-balances/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert (
        client.get(f"/hr/leave-balances/{created['id']}", headers=user_headers).status_code == 404
    )


def test_delete_leave_balance_not_found(client: TestClient):
    admin_headers = _location_admin_headers(client)

    response = client.delete(f"/hr/leave-balances/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404
