import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from datetime import date, time

import pytest
from conftest import clean_database
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import create_access_token, hash_password
from eop_api.db.engine import engine as app_engine
from eop_api.dependencies.employee_context import CurrentEmployeeContext, CurrentRequestContext
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
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.user import UserRepository


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Disposes the shared engine on shutdown, mirroring the real app's lifespan.

    Without this, pooled connections stay bound to this TestClient's event
    loop after it closes, and later tests crash trying to reuse them on a
    different (or already-closed) loop.
    """
    yield
    await app_engine.dispose()


app = FastAPI(lifespan=_lifespan)


@app.get("/__employee_context")
async def read_employee_context(employee_context: CurrentEmployeeContext) -> dict:
    return {
        "user_id": str(employee_context.user.id),
        "employee_id": str(employee_context.employee.id),
    }


@app.get("/__request_context")
async def read_request_context(request_context: CurrentRequestContext) -> dict:
    return {
        "user_id": str(request_context.user.id),
        "employee_id": str(request_context.employee_context.employee.id),
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


async def _link_employee(*, user_id: uuid.UUID) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        organization = await OrganizationRepository(session).create(name="Acme Corp")
        department = await DepartmentRepository(session).create(
            organization_id=organization.id, code="ENG", name="Engineering"
        )
        position = await PositionRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="ENG-1",
            name="Engineer",
        )
        team = await TeamRepository(session).create(
            organization_id=organization.id,
            department_id=department.id,
            code="BACKEND",
            name="Backend",
        )
        location_type = await LocationTypeRepository(session).create(name="Office", code="OFFICE")
        location = await LocationRepository(session).create(
            name="HQ", code="HQ", location_type_id=location_type.id
        )
        job_grade = await JobGradeRepository(session).create(code="L1", name="Engineer I", level=1)
        employment_type = await EmploymentTypeRepository(session).create(
            code="FT", name="Full-Time"
        )
        employment_status = await EmploymentStatusRepository(session).create(
            code="ACTIVE", name="Active"
        )
        shift = await ShiftRepository(session).create(
            code="DAY", name="Day Shift", start_time=time(9, 0), end_time=time(17, 0)
        )
        await HrEmployeeRepository(session).create(
            employee_number="EMP-1",
            first_name="Ada",
            last_name="Lovelace",
            full_name="Ada Lovelace",
            email="ada@example.com",
            organization_id=organization.id,
            department_id=department.id,
            position_id=position.id,
            team_id=team.id,
            location_id=location.id,
            job_grade_id=job_grade.id,
            employment_type_id=employment_type.id,
            employment_status_id=employment_status.id,
            shift_id=shift.id,
            hire_date=date(2024, 1, 15),
            employment_status="active",
            user_id=user_id,
        )
        await session.commit()
    await engine.dispose()


@pytest.fixture
def linked_user() -> User:
    user = asyncio.run(_create_user(email="linked@example.com", password="correct-horse"))
    asyncio.run(_link_employee(user_id=user.id))
    return user


def test_employee_context_resolves_linked_employee_for_authenticated_user(
    client: TestClient, linked_user: User
):
    token = create_access_token(subject=str(linked_user.id))

    response = client.get("/__employee_context", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["user_id"] == str(linked_user.id)


def test_employee_context_rejects_anonymous(client: TestClient):
    response = client.get("/__employee_context")

    assert response.status_code == 401


def test_request_context_carries_user_and_employee_context(client: TestClient, linked_user: User):
    token = create_access_token(subject=str(linked_user.id))

    response = client.get("/__request_context", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["user_id"] == str(linked_user.id)
    assert uuid.UUID(body["employee_id"])


def test_request_context_rejects_anonymous(client: TestClient):
    response = client.get("/__request_context")

    assert response.status_code == 401
