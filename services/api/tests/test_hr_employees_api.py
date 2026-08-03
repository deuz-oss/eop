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


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures all tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables. Truncating `organizations` with CASCADE also clears `departments`,
    `positions`, `teams`, and `hr_employees`, since they all reference
    `organizations` by foreign key (directly or transitively). `locations`,
    `location_types`, `job_grades`, `employment_types`, and
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
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Full-Time",
    code: str = "FT",
) -> dict:
    response = client.post(
        "/hr/employment-types", json={"name": name, "code": code}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_employment_status(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Active",
    code: str = "ACTIVE",
) -> dict:
    response = client.post(
        "/hr/employment-statuses", json={"name": name, "code": code}, headers=headers
    )
    assert response.status_code == 201
    return response.json()


def _create_shift(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Day Shift",
    code: str = "DAY",
) -> dict:
    response = client.post(
        "/hr/shifts",
        json={"code": code, "name": name, "start_time": "09:00:00", "end_time": "17:00:00"},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


class _Refs:
    def __init__(
        self,
        organization: dict,
        department: dict,
        position: dict,
        team: dict,
        location: dict,
        job_grade: dict,
        employment_type: dict,
        employment_status: dict,
        shift: dict,
    ):
        self.organization = organization
        self.department = department
        self.position = position
        self.team = team
        self.location = location
        self.job_grade = job_grade
        self.employment_type = employment_type
        self.employment_status = employment_status
        self.shift = shift


def _create_refs(client: TestClient, headers: dict[str, str], *, suffix: str = "") -> _Refs:
    organization = _create_organization(client, headers, name=f"Acme Corp{suffix}")
    department = _create_department(
        client, headers, code=f"ENG{suffix}", organization_id=organization["id"]
    )
    position = _create_position(
        client,
        headers,
        code=f"ENG-1{suffix}",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    team = _create_team(
        client,
        headers,
        code=f"BACKEND{suffix}",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    location_type = _create_location_type(client, headers, code=f"OFFICE{suffix}")
    location = _create_location(
        client, headers, code=f"HQ{suffix}", location_type_id=location_type["id"]
    )
    job_grade = _create_job_grade(
        client, headers, code=f"L1{suffix}", level=1 if suffix == "" else 2
    )
    employment_type = _create_employment_type(client, headers, code=f"FT{suffix}")
    employment_status = _create_employment_status(client, headers, code=f"ACTIVE{suffix}")
    shift = _create_shift(client, headers, code=f"DAY{suffix}")
    return _Refs(
        organization,
        department,
        position,
        team,
        location,
        job_grade,
        employment_type,
        employment_status,
        shift,
    )


def _employee_payload(refs: _Refs, **overrides) -> dict:
    payload = {
        "employee_number": "EMP-1",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "full_name": "Ada Lovelace",
        "email": "ada@example.com",
        "organization_id": refs.organization["id"],
        "department_id": refs.department["id"],
        "position_id": refs.position["id"],
        "team_id": refs.team["id"],
        "location_id": refs.location["id"],
        "job_grade_id": refs.job_grade["id"],
        "employment_type_id": refs.employment_type["id"],
        "employment_status_id": refs.employment_status["id"],
        "shift_id": refs.shift["id"],
        "hire_date": "2024-01-15",
        "employment_status": "active",
    }
    payload.update(overrides)
    return payload


def _create_employee(client: TestClient, headers: dict[str, str], refs: _Refs, **overrides) -> dict:
    response = client.post(
        "/hr/employees", json=_employee_payload(refs, **overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


def test_create_employee_requires_authentication(client: TestClient):
    response = client.post(
        "/hr/employees",
        json={
            "employee_number": "EMP-1",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "full_name": "Ada Lovelace",
            "email": "ada@example.com",
            "organization_id": str(uuid.uuid4()),
            "department_id": str(uuid.uuid4()),
            "position_id": str(uuid.uuid4()),
            "team_id": str(uuid.uuid4()),
            "location_id": str(uuid.uuid4()),
            "job_grade_id": str(uuid.uuid4()),
            "employment_type_id": str(uuid.uuid4()),
            "employment_status_id": str(uuid.uuid4()),
            "shift_id": str(uuid.uuid4()),
            "hire_date": "2024-01-15",
            "employment_status": "active",
        },
    )

    assert response.status_code == 401


def test_list_employees_requires_authentication(client: TestClient):
    response = client.get("/hr/employees")

    assert response.status_code == 401


def test_get_employee_requires_authentication(client: TestClient):
    response = client.get(f"/hr/employees/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_employee_requires_authentication(client: TestClient):
    response = client.put(f"/hr/employees/{uuid.uuid4()}", json={"full_name": "New Name"})

    assert response.status_code == 401


def test_delete_employee_requires_authentication(client: TestClient):
    response = client.delete(f"/hr/employees/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_employee(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)

    body = _create_employee(client, user_headers, refs)

    assert body["employee_number"] == "EMP-1"
    assert body["full_name"] == "Ada Lovelace"
    assert body["email"] == "ada@example.com"
    assert body["organization_id"] == refs.organization["id"]
    assert body["department_id"] == refs.department["id"]
    assert body["position_id"] == refs.position["id"]
    assert body["team_id"] == refs.team["id"]
    assert body["location_id"] == refs.location["id"]
    assert body["job_grade_id"] == refs.job_grade["id"]
    assert body["employment_type_id"] == refs.employment_type["id"]
    assert body["employment_status_id"] == refs.employment_status["id"]
    assert body["shift_id"] == refs.shift["id"]
    assert body["manager_id"] is None
    uuid.UUID(body["id"])


def test_create_employee_with_manager(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    manager = _create_employee(
        client,
        user_headers,
        refs,
        employee_number="MGR-1",
        email="grace@example.com",
        full_name="Grace Hopper",
    )

    report = _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
        manager_id=manager["id"],
    )

    assert report["manager_id"] == manager["id"]


def test_create_employee_rejects_blank_full_name(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees", json=_employee_payload(refs, full_name=""), headers=user_headers
    )

    assert response.status_code == 422


def test_create_employee_rejects_missing_organization(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, organization_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_missing_department(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, department_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_department_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    other_refs = _create_refs(client, user_headers, suffix="-2")

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, department_id=other_refs.department["id"]),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_employee_rejects_missing_position(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, position_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_position_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    other_refs = _create_refs(client, user_headers, suffix="-2")

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, position_id=other_refs.position["id"]),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_employee_rejects_missing_team(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, team_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_team_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    other_refs = _create_refs(client, user_headers, suffix="-2")

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, team_id=other_refs.team["id"]),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_employee_rejects_team_in_different_department(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    other_department = _create_department(
        client, user_headers, code="HR", name="HR", organization_id=refs.organization["id"]
    )
    other_team = _create_team(
        client,
        user_headers,
        code="HR-OPS",
        name="HR Ops",
        organization_id=refs.organization["id"],
        department_id=other_department["id"],
    )

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, team_id=other_team["id"]),
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_employee_rejects_missing_location(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, location_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_missing_job_grade(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, job_grade_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_missing_employment_type(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, employment_type_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_missing_employment_status(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, employment_status_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_missing_shift(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, shift_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_missing_manager(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, manager_id=str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_employee_rejects_duplicate_employee_number(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, email="other@example.com"),
        headers=user_headers,
    )

    assert response.status_code == 409


def test_create_employee_rejects_duplicate_email(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs)

    response = client.post(
        "/hr/employees",
        json=_employee_payload(refs, employee_number="EMP-2"),
        headers=user_headers,
    )

    assert response.status_code == 409


def test_get_employee(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.get(f"/hr/employees/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["full_name"] == "Ada Lovelace"


def test_get_employee_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/hr/employees/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_employees(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs)
    _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
    )

    response = client.get("/hr/employees", headers=user_headers)

    assert response.status_code == 200
    names = {employee["full_name"] for employee in response.json()}
    assert {"Ada Lovelace", "Alan Turing"}.issubset(names)


def test_list_employees_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    for i in range(3):
        _create_employee(
            client, user_headers, refs, employee_number=f"EMP-{i}", email=f"emp{i}@example.com"
        )

    response = client.get("/hr/employees/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_employees_paginated_custom_offset(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    for i in range(5):
        _create_employee(
            client, user_headers, refs, employee_number=f"EMP-{i}", email=f"emp{i}@example.com"
        )

    response = client.get("/hr/employees/paginated", headers=user_headers, params={"offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_employees_paginated_custom_limit(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    for i in range(5):
        _create_employee(
            client, user_headers, refs, employee_number=f"EMP-{i}", email=f"emp{i}@example.com"
        )

    response = client.get("/hr/employees/paginated", headers=user_headers, params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_employees_paginated_limit_above_maximum_is_clamped(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs)

    response = client.get("/hr/employees/paginated", headers=user_headers, params={"limit": 500})

    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_list_employees_paginated_negative_offset_is_rejected(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/hr/employees/paginated", headers=user_headers, params={"offset": -1})

    assert response.status_code == 422


def test_list_employees_paginated_search_by_employee_number(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs, employee_number="ENG-ALPHA")
    _create_employee(
        client,
        user_headers,
        refs,
        employee_number="ENG-BETA",
        email="alan@example.com",
        full_name="Alan Turing",
    )

    response = client.get("/hr/employees/paginated", headers=user_headers, params={"q": "alpha"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["employee_number"] == "ENG-ALPHA"


def test_list_employees_paginated_search_by_full_name(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs)
    _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        first_name="Alan",
        last_name="Turing",
        email="alan@example.com",
        full_name="Alan Turing",
    )

    response = client.get("/hr/employees/paginated", headers=user_headers, params={"q": "lovelace"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["full_name"] == "Ada Lovelace"


def test_list_employees_paginated_filter_by_organization_id(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    other_refs = _create_refs(client, user_headers, suffix="-2")
    _create_employee(client, user_headers, refs)
    _create_employee(
        client,
        user_headers,
        other_refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
    )

    response = client.get(
        "/hr/employees/paginated",
        headers=user_headers,
        params={"organization_id": refs.organization["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["organization_id"] == refs.organization["id"]


def test_list_employees_paginated_filter_by_employment_status(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs, employment_status="active")
    _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
        employment_status="terminated",
    )

    response = client.get(
        "/hr/employees/paginated", headers=user_headers, params={"employment_status": "active"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["employment_status"] == "active"


def test_list_employees_paginated_no_query_returns_all(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs)
    _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
    )

    response = client.get("/hr/employees/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_update_employee(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}", json={"full_name": "Ada Byron"}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["full_name"] == "Ada Byron"


def test_update_employee_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/hr/employees/{uuid.uuid4()}", json={"full_name": "Nobody"}, headers=user_headers
    )

    assert response.status_code == 404


def test_update_employee_rejects_missing_department(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"department_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_employee_rejects_department_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    other_refs = _create_refs(client, user_headers, suffix="-2")
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"department_id": other_refs.department["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_employee_changes_job_grade(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    other_job_grade = _create_job_grade(client, user_headers, code="L2", level=2)
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"job_grade_id": other_job_grade["id"]},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["job_grade_id"] == other_job_grade["id"]


def test_update_employee_rejects_missing_job_grade(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"job_grade_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_employee_changes_employment_type(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    other_employment_type = _create_employment_type(client, user_headers, code="PT")
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"employment_type_id": other_employment_type["id"]},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["employment_type_id"] == other_employment_type["id"]


def test_update_employee_rejects_missing_employment_type(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"employment_type_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_employee_changes_employment_status(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    other_employment_status = _create_employment_status(client, user_headers, code="LEAVE")
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"employment_status_id": other_employment_status["id"]},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["employment_status_id"] == other_employment_status["id"]


def test_update_employee_rejects_missing_employment_status(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"employment_status_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_employee_changes_shift(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    other_shift = _create_shift(client, user_headers, code="NIGHT")
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"shift_id": other_shift["id"]},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["shift_id"] == other_shift["id"]


def test_update_employee_rejects_missing_shift(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}",
        json={"shift_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_employee_accepts_existing_manager(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    manager = _create_employee(
        client,
        user_headers,
        refs,
        employee_number="MGR-1",
        email="grace@example.com",
        full_name="Grace Hopper",
    )
    employee = _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
    )

    response = client.put(
        f"/hr/employees/{employee['id']}", json={"manager_id": manager["id"]}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["manager_id"] == manager["id"]


def test_update_employee_rejects_self_manager(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.put(
        f"/hr/employees/{created['id']}", json={"manager_id": created["id"]}, headers=user_headers
    )

    assert response.status_code == 422


def test_update_employee_rejects_duplicate_employee_number(
    client: TestClient, user_headers: dict[str, str]
):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs)
    other = _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
    )

    response = client.put(
        f"/hr/employees/{other['id']}", json={"employee_number": "EMP-1"}, headers=user_headers
    )

    assert response.status_code == 409


def test_update_employee_rejects_duplicate_email(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    _create_employee(client, user_headers, refs)
    other = _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
    )

    response = client.put(
        f"/hr/employees/{other['id']}", json={"email": "ada@example.com"}, headers=user_headers
    )

    assert response.status_code == 409


def test_delete_employee(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    created = _create_employee(client, user_headers, refs)

    response = client.delete(f"/hr/employees/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/hr/employees/{created['id']}", headers=user_headers).status_code == 404


def test_delete_employee_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/hr/employees/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_delete_manager_with_reports_fails(client: TestClient, user_headers: dict[str, str]):
    refs = _create_refs(client, user_headers)
    manager = _create_employee(
        client,
        user_headers,
        refs,
        employee_number="MGR-1",
        email="grace@example.com",
        full_name="Grace Hopper",
    )
    _create_employee(
        client,
        user_headers,
        refs,
        employee_number="EMP-2",
        email="alan@example.com",
        full_name="Alan Turing",
        manager_id=manager["id"],
    )

    # TestClient re-raises unhandled server exceptions by default; disable that
    # here so the FK violation surfaces as the real 500 response it produces in
    # production, instead of propagating into the test as a raw exception.
    with TestClient(app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.delete(f"/hr/employees/{manager['id']}", headers=user_headers)

    assert response.status_code == 500
