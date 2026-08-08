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
    """Ensures all tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables. Truncating `organizations` and `shifts` with CASCADE also clears
    `departments`, `positions`, `teams`, `hr_employees`, and `payslips`.
    `locations`, `location_types`, `job_grades`, `employment_types`,
    `employment_statuses`, and `payroll_runs` don't depend on
    `organizations`, so they're truncated explicitly.
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
                    "job_grades, employment_types, employment_statuses, shifts, "
                    "payroll_runs, users CASCADE"
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
    """An authenticated user who does not own the payslip under test."""
    return asyncio.run(_create_user(email="other@example.com", password="other-pass"))


@pytest.fixture
def other_headers(client: TestClient, other: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "other-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_admin(user_id: uuid.UUID) -> None:
    """Grants the `admin` role directly at the DB layer.

    Mirrors `test_roles_api.py`'s `_seed_admin`: `PayrollRun` is Role Based
    (`RequireRole("admin")`), so creating one for these Payslip tests requires
    an admin-privileged caller, separate from the employee-owner caller that
    creates their own `Payslip`.
    """
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
def admin_user() -> User:
    return asyncio.run(_create_user(email="admin@example.com", password="admin-pass"))


@pytest.fixture
def admin_headers(client: TestClient, admin_user: User) -> dict[str, str]:
    asyncio.run(_seed_admin(admin_user.id))

    response = client.post(
        "/auth/login", json={"email": "admin@example.com", "password": "admin-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_organization(client: TestClient, headers: dict[str, str], *, name: str) -> dict:
    response = client.post("/organizations", json={"name": name})
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
    location_type = _create_location_type(client, headers, code=f"OFFICE-{suffix}")
    location = _create_location(
        client, headers, location_type_id=location_type["id"], code=f"HQ-{suffix}"
    )
    job_grade = _create_job_grade(
        client, headers, code=f"L1-{suffix}", level=int(suffix[:4], 16) + 1
    )
    employment_type = _create_employment_type(client, headers, code=f"FT-{suffix}")
    employment_status = _create_employment_status(client, headers, code=f"ACTIVE-{suffix}")
    shift = _create_shift(client, headers, code=f"DAY-{suffix}")

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


def _create_payroll_run(
    client: TestClient, headers: dict[str, str], *, code: str = "RUN-001", name: str = "First Run"
) -> dict:
    response = client.post(
        "/hr/payroll-runs", json={"code": code, "name": name}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_payslip(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_id: str,
    payroll_run_id: str,
    gross_salary_amount: str = "1000.00",
    gross_salary_currency: str = "IDR",
    net_salary_amount: str = "1000.00",
    net_salary_currency: str = "IDR",
) -> dict:
    response = client.post(
        "/payslips",
        json={
            "employee_id": employee_id,
            "payroll_run_id": payroll_run_id,
            "gross_salary_amount": gross_salary_amount,
            "gross_salary_currency": gross_salary_currency,
            "net_salary_amount": net_salary_amount,
            "net_salary_currency": net_salary_currency,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def test_create_payslip_requires_authentication(client: TestClient):
    response = client.post(
        "/payslips",
        json={
            "employee_id": str(uuid.uuid4()),
            "payroll_run_id": str(uuid.uuid4()),
            "gross_salary_amount": "1000.00",
            "gross_salary_currency": "IDR",
            "net_salary_amount": "1000.00",
            "net_salary_currency": "IDR",
        },
    )

    assert response.status_code == 401


def test_list_payslips_requires_authentication(client: TestClient):
    response = client.get("/payslips")

    assert response.status_code == 401


def test_get_payslip_requires_authentication(client: TestClient):
    response = client.get(f"/payslips/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_payslip(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    payroll_run = _create_payroll_run(client, admin_headers)

    body = _create_payslip(
        client, user_headers, employee_id=employee["id"], payroll_run_id=payroll_run["id"]
    )

    assert body["employee_id"] == employee["id"]
    assert body["payroll_run_id"] == payroll_run["id"]
    assert body["gross_salary_amount"] == "1000.00"
    assert body["net_salary_amount"] == "1000.00"
    uuid.UUID(body["id"])


def test_create_payslip_rejects_missing_employee(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))
    payroll_run = _create_payroll_run(client, admin_headers)

    response = client.post(
        "/payslips",
        json={
            "employee_id": str(uuid.uuid4()),
            "payroll_run_id": payroll_run["id"],
            "gross_salary_amount": "1000.00",
            "gross_salary_currency": "IDR",
            "net_salary_amount": "1000.00",
            "net_salary_currency": "IDR",
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_payslip_rejects_missing_payroll_run(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/payslips",
        json={
            "employee_id": employee["id"],
            "payroll_run_id": str(uuid.uuid4()),
            "gross_salary_amount": "1000.00",
            "gross_salary_currency": "IDR",
            "net_salary_amount": "1000.00",
            "net_salary_currency": "IDR",
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_payslip_forbidden_for_non_owner(
    client: TestClient,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers)
    _create_employee(client, user_headers, user_id=str(other.id))
    payroll_run = _create_payroll_run(client, admin_headers)

    response = client.post(
        "/payslips",
        json={
            "employee_id": employee["id"],
            "payroll_run_id": payroll_run["id"],
            "gross_salary_amount": "1000.00",
            "gross_salary_currency": "IDR",
            "net_salary_amount": "1000.00",
            "net_salary_currency": "IDR",
        },
        headers=other_headers,
    )

    assert response.status_code == 403


def test_get_payslip(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    payroll_run = _create_payroll_run(client, admin_headers)
    created = _create_payslip(
        client, user_headers, employee_id=employee["id"], payroll_run_id=payroll_run["id"]
    )

    response = client.get(f"/payslips/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_payslip_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.get(f"/payslips/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_get_payslip_forbidden_for_non_owner(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    payroll_run = _create_payroll_run(client, admin_headers)
    created = _create_payslip(
        client, user_headers, employee_id=employee["id"], payroll_run_id=payroll_run["id"]
    )
    _create_employee(client, user_headers, user_id=str(other.id))

    response = client.get(f"/payslips/{created['id']}", headers=other_headers)

    assert response.status_code == 403


def test_list_payslips_returns_only_owned(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(client, user_headers, user_id=str(other.id))
    payroll_run = _create_payroll_run(client, admin_headers)
    _create_payslip(
        client, user_headers, employee_id=employee["id"], payroll_run_id=payroll_run["id"]
    )
    _create_payslip(
        client, other_headers, employee_id=other_employee["id"], payroll_run_id=payroll_run["id"]
    )

    response = client.get("/payslips", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["employee_id"] == employee["id"]
