import asyncio
import uuid
from collections.abc import Generator
from datetime import datetime
from decimal import Decimal

import pytest
from conftest import clean_database
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.achievement import AchievementRepository
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
from eop_api.repositories.target import TargetRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.user import UserRepository

# Reporting Authorization: Role Based (`RequireRole("admin")`), mirroring
# `test_targets_api.py`'s/`test_achievements_api.py`'s exact fixture/test
# pattern.


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


async def _create_achievement_chain(*, suffix: str) -> None:
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
        target = await TargetRepository(session).create(
            employee_id=employee.id,
            kpi_id=kpi.id,
            period_year=2026,
            period_month=8,
            goal_value=Decimal("95.5"),
        )
        await AchievementRepository(session).create(
            target_id=target.id, actual_value=Decimal("90.25")
        )
        await session.commit()
    await engine.dispose()


@pytest.fixture
def achievement_chain() -> None:
    asyncio.run(_create_achievement_chain(suffix=uuid.uuid4().hex[:8]))


def test_list_reporting_requires_authentication(client: TestClient):
    assert client.get("/performance/reporting").status_code == 401


def test_list_reporting_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    assert client.get("/performance/reporting", headers=member_headers).status_code == 403


def test_list_reporting_empty(client: TestClient, admin_headers: dict[str, str]):
    response = client.get("/performance/reporting", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_reporting_returns_line(
    client: TestClient, admin_headers: dict[str, str], achievement_chain: None
):
    response = client.get("/performance/reporting", headers=admin_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    line = body["items"][0]
    assert line["kpi_code"].startswith("VCR-")
    assert line["employee_full_name"] == "Ada Lovelace"
    assert line["period_year"] == 2026
    assert line["period_month"] == 8
    assert line["goal_value"] == "95.500000"
    assert line["actual_value"] == "90.250000"
    uuid.UUID(line["achievement_id"])
    uuid.UUID(line["target_id"])
    uuid.UUID(line["kpi_id"])
    uuid.UUID(line["employee_id"])


def test_list_reporting_filters_by_unmatched_period(
    client: TestClient, admin_headers: dict[str, str], achievement_chain: None
):
    response = client.get(
        "/performance/reporting",
        headers=admin_headers,
        params={"period_year": 2026, "period_month": 9},
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_list_reporting_paginated(
    client: TestClient, admin_headers: dict[str, str], achievement_chain: None
):
    response = client.get(
        "/performance/reporting", headers=admin_headers, params={"offset": 0, "limit": 1}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 1
    assert len(body["items"]) == 1
