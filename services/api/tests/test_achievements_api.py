import asyncio
import uuid
from collections.abc import Generator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.kpi import KpiRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.user import UserRepository

# Achievement Authorization: Role Based (`RequireRole("admin")`), mirroring
# `test_targets_api.py`'s exact fixture/test pattern.


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
                    "job_grades, employment_types, employment_statuses, shifts, "
                    "kpis, users CASCADE"
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


async def _create_hr_employee_and_kpi(*, suffix: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Direct repository scaffolding for the `HrEmployee`/`Kpi` prerequisites
    -- Achievement is `RequireRole("admin")`-gated only, no
    `CurrentRequestContext` resolution is involved, so no `User`/`user_id`
    link is needed here, mirroring `test_targets_api.py`."""
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name=f"Acme Corp {suffix}")
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code=f"ENG-{suffix}", name="Engineering"
        )
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code=f"ENG-1-{suffix}",
            name="Engineer",
        )
        team = await TeamRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code=f"BACKEND-{suffix}",
            name="Backend Team",
        )
        location_type = await LocationTypeRepository(session).create(
            code=f"OFFICE-{suffix}", name="Office"
        )
        location = await LocationRepository(session).create(
            code=f"HQ-{suffix}", name="HQ", location_type_id=location_type.id
        )
        job_grade = await JobGradeRepository(session).create(
            code=f"L1-{suffix}", name="Junior", level=1
        )
        employment_type = await EmploymentTypeRepository(session).create(
            code=f"FT-{suffix}", name="Full-Time"
        )
        employment_status = await EmploymentStatusRepository(session).create(
            code=f"ACTIVE-{suffix}", name="Active"
        )
        shift = await ShiftRepository(session).create(
            code=f"DAY-{suffix}",
            name="Day Shift",
            start_time=datetime(2024, 1, 1, 9, 0).time(),
            end_time=datetime(2024, 1, 1, 17, 0).time(),
        )
        employee = await HrEmployeeRepository(session).create(
            employee_number=f"EMP-{suffix}",
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email=f"ada-{suffix}@example.com",
            organization_id=organization.id,
            department_id=department.id,
            position_id=position.id,
            team_id=team.id,
            location_id=location.id,
            job_grade_id=job_grade.id,
            employment_type_id=employment_type.id,
            employment_status_id=employment_status.id,
            shift_id=shift.id,
            hire_date=datetime(2024, 1, 15).date(),
            employment_status="active",
        )
        kpi = await KpiRepository(session).create(
            code=f"VCR-{suffix}", name="Visit Compliance Rate", unit="%"
        )
        await session.commit()
        employee_id, kpi_id = employee.id, kpi.id
    await engine.dispose()
    return employee_id, kpi_id


@pytest.fixture
def prerequisites() -> tuple[uuid.UUID, uuid.UUID]:
    return asyncio.run(_create_hr_employee_and_kpi(suffix=uuid.uuid4().hex[:8]))


@pytest.fixture
def employee_id(prerequisites: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    return prerequisites[0]


@pytest.fixture
def kpi_id(prerequisites: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    return prerequisites[1]


def _create_target(
    client: TestClient,
    headers: dict[str, str],
    *,
    kpi_id: uuid.UUID,
    employee_id: uuid.UUID,
    period_year: int = 2026,
    period_month: int = 8,
    goal_value: str = "95.5",
) -> dict:
    body = {
        "kpi_id": str(kpi_id),
        "employee_id": str(employee_id),
        "period_year": period_year,
        "period_month": period_month,
        "goal_value": goal_value,
    }
    response = client.post("/targets", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def target_id(
    client: TestClient, admin_headers: dict[str, str], kpi_id: uuid.UUID, employee_id: uuid.UUID
) -> uuid.UUID:
    created = _create_target(client, admin_headers, kpi_id=kpi_id, employee_id=employee_id)
    return uuid.UUID(created["id"])


def _create_achievement(
    client: TestClient,
    headers: dict[str, str],
    *,
    target_id: uuid.UUID,
    actual_value: str = "90.25",
) -> dict:
    body = {"target_id": str(target_id), "actual_value": actual_value}
    response = client.post("/achievements", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_achievement_requires_authentication(client: TestClient):
    response = client.post(
        "/achievements", json={"target_id": str(uuid.uuid4()), "actual_value": "1"}
    )
    assert response.status_code == 401


def test_list_achievements_requires_authentication(client: TestClient):
    assert client.get("/achievements").status_code == 401


def test_get_achievement_requires_authentication(client: TestClient):
    assert client.get(f"/achievements/{uuid.uuid4()}").status_code == 401


def test_update_achievement_requires_authentication(client: TestClient):
    response = client.put(f"/achievements/{uuid.uuid4()}", json={"actual_value": "1"})
    assert response.status_code == 401


def test_delete_achievement_requires_authentication(client: TestClient):
    assert client.delete(f"/achievements/{uuid.uuid4()}").status_code == 401


def test_create_achievement_rejects_non_admin(
    client: TestClient, member_headers: dict[str, str], target_id: uuid.UUID
):
    response = client.post(
        "/achievements",
        json={"target_id": str(target_id), "actual_value": "1"},
        headers=member_headers,
    )
    assert response.status_code == 403


def test_list_achievements_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    assert client.get("/achievements", headers=member_headers).status_code == 403


def test_get_achievement_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/achievements/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_update_achievement_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.put(
        f"/achievements/{uuid.uuid4()}", json={"actual_value": "1"}, headers=member_headers
    )
    assert response.status_code == 403


def test_delete_achievement_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.delete(f"/achievements/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_create_achievement(
    client: TestClient, admin_headers: dict[str, str], target_id: uuid.UUID
):
    body = _create_achievement(client, admin_headers, target_id=target_id)

    assert body["target_id"] == str(target_id)
    assert body["actual_value"] == "90.25"
    uuid.UUID(body["id"])


def test_create_achievement_rejects_missing_target(
    client: TestClient, admin_headers: dict[str, str]
):
    response = client.post(
        "/achievements",
        json={"target_id": str(uuid.uuid4()), "actual_value": "1"},
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_create_achievement_rejects_duplicate_target(
    client: TestClient, admin_headers: dict[str, str], target_id: uuid.UUID
):
    _create_achievement(client, admin_headers, target_id=target_id)

    response = client.post(
        "/achievements",
        json={"target_id": str(target_id), "actual_value": "1"},
        headers=admin_headers,
    )
    assert response.status_code == 409


def test_get_achievement(client: TestClient, admin_headers: dict[str, str], target_id: uuid.UUID):
    created = _create_achievement(client, admin_headers, target_id=target_id)

    response = client.get(f"/achievements/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_achievement_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(f"/achievements/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404


def test_list_achievements_paginated(
    client: TestClient, admin_headers: dict[str, str], target_id: uuid.UUID
):
    _create_achievement(client, admin_headers, target_id=target_id)

    response = client.get("/achievements/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_update_achievement_changes_actual_value(
    client: TestClient, admin_headers: dict[str, str], target_id: uuid.UUID
):
    created = _create_achievement(client, admin_headers, target_id=target_id)

    response = client.put(
        f"/achievements/{created['id']}", json={"actual_value": "150.75"}, headers=admin_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["actual_value"] == "150.750000"
    assert body["target_id"] == created["target_id"]


def test_update_achievement_ignores_target_id_field(
    client: TestClient, admin_headers: dict[str, str], target_id: uuid.UUID
):
    """`AchievementUpdate` has no `target_id` field, so an extra key in the
    request body is silently ignored by Pydantic rather than applied --
    identity remains immutable."""
    created = _create_achievement(client, admin_headers, target_id=target_id)

    response = client.put(
        f"/achievements/{created['id']}",
        json={"actual_value": "1", "target_id": str(uuid.uuid4())},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["target_id"] == created["target_id"]


def test_update_achievement_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/achievements/{uuid.uuid4()}", json={"actual_value": "1"}, headers=admin_headers
    )
    assert response.status_code == 404


def test_delete_achievement(
    client: TestClient, admin_headers: dict[str, str], target_id: uuid.UUID
):
    created = _create_achievement(client, admin_headers, target_id=target_id)

    response = client.delete(f"/achievements/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"/achievements/{created['id']}", headers=admin_headers).status_code == 404


def test_delete_achievement_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/achievements/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404


def test_target_deletion_restricted_while_achievement_exists(
    client: TestClient, admin_headers: dict[str, str], target_id: uuid.UUID
):
    """`Achievement.target_id` is `ON DELETE RESTRICT` -- deleting a `Target`
    with an `Achievement` still referencing it violates the FK constraint at
    the database level. `TargetService.delete` does not catch this (no
    service in this repository translates a RESTRICT violation into a
    friendly error), so it propagates as an `IntegrityError` -- `TestClient`
    re-raises unhandled exceptions by default rather than returning the
    500 response `unhandled_exception_handler` would produce in production."""
    _create_achievement(client, admin_headers, target_id=target_id)

    with pytest.raises(IntegrityError):
        client.delete(f"/targets/{target_id}", headers=admin_headers)
