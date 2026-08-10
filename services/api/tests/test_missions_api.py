import asyncio
import uuid
from collections.abc import Generator
from datetime import datetime

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
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.location_type import LocationTypeRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.store import StoreRepository
from eop_api.repositories.store_type import StoreTypeRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.user import UserRepository

# Mission Authorization: Role Based (`RequireRole("admin")`), mirroring
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
                    "store_types, users, roles CASCADE"
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


async def _create_employee_and_store(*, suffix: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Direct repository scaffolding for the `HrEmployee`/`Store`
    prerequisites -- Mission is `RequireRole("admin")`-gated only, no
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
            code=f"L1-{suffix}", name="Junior", level=int(suffix, 16) % 1000000 + 1
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
        store_type = await StoreTypeRepository(session).create(
            code=f"MT-{suffix}", name="Modern Trade"
        )
        store = await StoreRepository(session).create(
            code=f"ST-{suffix}",
            name="Indomaret Sudirman",
            organization_id=organization.id,
            store_type_id=store_type.id,
        )
        await session.commit()
        employee_id, store_id = employee.id, store.id
    await engine.dispose()
    return employee_id, store_id


@pytest.fixture
def prerequisites() -> tuple[uuid.UUID, uuid.UUID]:
    return asyncio.run(_create_employee_and_store(suffix=uuid.uuid4().hex[:8]))


@pytest.fixture
def employee_id(prerequisites: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    return prerequisites[0]


@pytest.fixture
def store_id(prerequisites: tuple[uuid.UUID, uuid.UUID]) -> uuid.UUID:
    return prerequisites[1]


def _create_mission(
    client: TestClient,
    headers: dict[str, str],
    *,
    employee_id: uuid.UUID,
    store_id: uuid.UUID,
    scheduled_date: str = "2026-01-05",
) -> dict:
    body = {
        "employee_id": str(employee_id),
        "store_id": str(store_id),
        "scheduled_date": scheduled_date,
    }
    response = client.post("/missions", json=body, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_mission_requires_authentication(client: TestClient):
    response = client.post(
        "/missions",
        json={
            "employee_id": str(uuid.uuid4()),
            "store_id": str(uuid.uuid4()),
            "scheduled_date": "2026-01-05",
        },
    )
    assert response.status_code == 401


def test_list_missions_requires_authentication(client: TestClient):
    assert client.get("/missions").status_code == 401


def test_get_mission_requires_authentication(client: TestClient):
    assert client.get(f"/missions/{uuid.uuid4()}").status_code == 401


def test_update_mission_requires_authentication(client: TestClient):
    response = client.put(f"/missions/{uuid.uuid4()}", json={"scheduled_date": "2026-01-06"})
    assert response.status_code == 401


def test_delete_mission_requires_authentication(client: TestClient):
    assert client.delete(f"/missions/{uuid.uuid4()}").status_code == 401


def test_create_mission_rejects_non_admin(
    client: TestClient,
    member_headers: dict[str, str],
    employee_id: uuid.UUID,
    store_id: uuid.UUID,
):
    response = client.post(
        "/missions",
        json={
            "employee_id": str(employee_id),
            "store_id": str(store_id),
            "scheduled_date": "2026-01-05",
        },
        headers=member_headers,
    )
    assert response.status_code == 403


def test_list_missions_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    assert client.get("/missions", headers=member_headers).status_code == 403


def test_get_mission_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.get(f"/missions/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_update_mission_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.put(
        f"/missions/{uuid.uuid4()}", json={"scheduled_date": "2026-01-06"}, headers=member_headers
    )
    assert response.status_code == 403


def test_delete_mission_rejects_non_admin(client: TestClient, member_headers: dict[str, str]):
    response = client.delete(f"/missions/{uuid.uuid4()}", headers=member_headers)
    assert response.status_code == 403


def test_create_mission(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    body = _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)

    assert body["employee_id"] == str(employee_id)
    assert body["store_id"] == str(store_id)
    assert body["scheduled_date"] == "2026-01-05"
    uuid.UUID(body["id"])


def test_create_mission_rejects_missing_employee(
    client: TestClient, admin_headers: dict[str, str], store_id: uuid.UUID
):
    response = client.post(
        "/missions",
        json={
            "employee_id": str(uuid.uuid4()),
            "store_id": str(store_id),
            "scheduled_date": "2026-01-05",
        },
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_create_mission_rejects_missing_store(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID
):
    response = client.post(
        "/missions",
        json={
            "employee_id": str(employee_id),
            "store_id": str(uuid.uuid4()),
            "scheduled_date": "2026-01-05",
        },
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_create_mission_allows_duplicate_employee_store_date(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)

    response = client.post(
        "/missions",
        json={
            "employee_id": str(employee_id),
            "store_id": str(store_id),
            "scheduled_date": "2026-01-05",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201


def test_get_mission(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    created = _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)

    response = client.get(f"/missions/{created['id']}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_mission_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.get(f"/missions/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404


def test_list_missions(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)

    response = client.get("/missions", headers=admin_headers)

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_list_missions_paginated(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)

    response = client.get("/missions/paginated", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_list_missions_paginated_filters_by_employee_id(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)

    response = client.get(
        "/missions/paginated", headers=admin_headers, params={"employee_id": str(uuid.uuid4())}
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


def test_update_mission_reassigns_employee(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    created = _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)
    other_employee_id, _ = asyncio.run(_create_employee_and_store(suffix=uuid.uuid4().hex[:8]))

    response = client.put(
        f"/missions/{created['id']}",
        json={"employee_id": str(other_employee_id)},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["employee_id"] == str(other_employee_id)
    assert body["store_id"] == str(store_id)


def test_update_mission_reschedules_date(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    created = _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)

    response = client.put(
        f"/missions/{created['id']}",
        json={"scheduled_date": "2026-02-01"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["scheduled_date"] == "2026-02-01"


def test_update_mission_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/missions/{uuid.uuid4()}", json={"scheduled_date": "2026-01-06"}, headers=admin_headers
    )
    assert response.status_code == 404


def test_delete_mission(
    client: TestClient, admin_headers: dict[str, str], employee_id: uuid.UUID, store_id: uuid.UUID
):
    created = _create_mission(client, admin_headers, employee_id=employee_id, store_id=store_id)

    response = client.delete(f"/missions/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"/missions/{created['id']}", headers=admin_headers).status_code == 404


def test_delete_mission_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/missions/{uuid.uuid4()}", headers=admin_headers)
    assert response.status_code == 404
