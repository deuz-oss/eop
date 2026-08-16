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

DEFAULT_VISITED_AT = "2026-01-05T09:00:00Z"


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
                    "store_types, users CASCADE"
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
    """An authenticated user who does not own the visit under test."""
    return asyncio.run(_create_user(email="other@example.com", password="other-pass"))


@pytest.fixture
def other_headers(client: TestClient, other: User) -> dict[str, str]:
    response = client.post(
        "/auth/login", json={"email": "other@example.com", "password": "other-pass"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user() -> User:
    """Store/StoreType are `RequireRole("admin")`-gated, distinct from
    Visit's own Owner Only policy -- this user only exists to create the
    `Store` prerequisite fixture, never as a Visit actor."""
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


def _location_admin_headers(client: TestClient) -> dict[str, str]:
    """A throwaway admin session used only to satisfy the admin-only
    Location/LocationType write requirement during master-data bootstrap --
    the employee/user actually under test keeps its own identity. Reuses this
    file's existing `_seed_admin` role-assignment helper."""
    suffix = uuid.uuid4().hex[:8]
    email = f"location-admin-{suffix}@example.com"
    user = asyncio.run(_create_user(email=email, password="admin-pass"))
    asyncio.run(_seed_admin(user.id))
    response = client.post("/auth/login", json={"email": email, "password": "admin-pass"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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
) -> dict:
    """Each call creates its own HR master-data scaffolding, suffixed by a
    fresh id so multiple employees (e.g. owner + non-owner) can be created
    within the same test without violating uniqueness constraints."""
    suffix = uuid.uuid4().hex[:8]
    organization = client.post(
        "/organizations", json={"name": f"Acme Corp {suffix}"}, headers=headers
    ).json()
    department = client.post(
        "/departments",
        json={
            "name": "Engineering",
            "code": f"ENG-{suffix}",
            "organization_id": organization["id"],
        },
        headers=headers,
    ).json()
    position = client.post(
        "/positions",
        json={
            "name": "Engineer",
            "code": f"POS-{suffix}",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=headers,
    ).json()
    team = client.post(
        "/teams",
        json={
            "name": "Backend",
            "code": f"TEAM-{suffix}",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=headers,
    ).json()
    location_admin_headers = _location_admin_headers(client)
    location_type = client.post(
        "/location-types",
        json={"name": "Office", "code": f"OFFICE-{suffix}"},
        headers=location_admin_headers,
    ).json()
    location = client.post(
        "/locations",
        json={"name": "HQ", "code": f"HQ-{suffix}", "location_type_id": location_type["id"]},
        headers=location_admin_headers,
    ).json()
    job_grade = client.post(
        "/hr/job-grades",
        json={"name": "Engineer I", "code": f"L1-{suffix}", "level": int(suffix[:4], 16) + 1},
        headers=headers,
    ).json()
    employment_type = client.post(
        "/hr/employment-types", json={"name": "Full-Time", "code": f"FT-{suffix}"}, headers=headers
    ).json()
    employment_status = client.post(
        "/hr/employment-statuses",
        json={"name": "Active", "code": f"ACTIVE-{suffix}"},
        headers=headers,
    ).json()
    shift = client.post(
        "/hr/shifts",
        json={
            "code": f"DAY-{suffix}",
            "name": "Day Shift",
            "start_time": "09:00:00",
            "end_time": "17:00:00",
        },
        headers=headers,
    ).json()

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

    response = client.post("/hr/employees", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def _create_store(client: TestClient, headers: dict[str, str]) -> dict:
    suffix = uuid.uuid4().hex[:8]
    organization = client.post(
        "/organizations", json={"name": f"Store Org {suffix}"}, headers=headers
    ).json()
    store_type = client.post(
        "/store-types", json={"code": f"MT-{suffix}", "name": "Modern Trade"}, headers=headers
    ).json()
    response = client.post(
        "/stores",
        json={
            "code": f"ST-{suffix}",
            "name": "Indomaret Sudirman",
            "organization_id": organization["id"],
            "store_type_id": store_type["id"],
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _visit_payload(employee_id: str, store_id: str, **overrides) -> dict:
    payload = {"employee_id": employee_id, "store_id": store_id, "visited_at": DEFAULT_VISITED_AT}
    payload.update(overrides)
    return payload


def _create_visit(
    client: TestClient, headers: dict[str, str], employee_id: str, store_id: str, **overrides
) -> dict:
    response = client.post(
        "/visits", json=_visit_payload(employee_id, store_id, **overrides), headers=headers
    )
    assert response.status_code == 201
    return response.json()


def test_create_visit_requires_authentication(client: TestClient):
    response = client.post("/visits", json=_visit_payload(str(uuid.uuid4()), str(uuid.uuid4())))

    assert response.status_code == 401


def test_list_visits_requires_authentication(client: TestClient):
    assert client.get("/visits").status_code == 401


def test_get_visit_requires_authentication(client: TestClient):
    assert client.get(f"/visits/{uuid.uuid4()}").status_code == 401


def test_update_visit_requires_authentication(client: TestClient):
    response = client.put(f"/visits/{uuid.uuid4()}", json={"notes": "x"})
    assert response.status_code == 401


def test_delete_visit_requires_authentication(client: TestClient):
    assert client.delete(f"/visits/{uuid.uuid4()}").status_code == 401


def test_create_visit(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)

    body = _create_visit(client, user_headers, employee["id"], store["id"], notes="First visit")

    assert body["employee_id"] == employee["id"]
    assert body["store_id"] == store["id"]
    assert body["notes"] == "First visit"
    uuid.UUID(body["id"])


def test_create_visit_rejects_missing_employee(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)

    response = client.post(
        "/visits",
        json=_visit_payload(str(uuid.uuid4()), store["id"]),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_visit_rejects_missing_store(
    client: TestClient, user: User, user_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))

    response = client.post(
        "/visits",
        json=_visit_payload(employee["id"], str(uuid.uuid4())),
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_visit_forbidden_for_non_owner(
    client: TestClient,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers)
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
    store = _create_store(client, admin_headers)

    response = client.post(
        "/visits",
        json=_visit_payload(employee["id"], store["id"]),
        headers=other_headers,
    )

    assert response.status_code == 403


def test_get_visit(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])

    response = client.get(f"/visits/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]


def test_get_visit_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.get(f"/visits/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_get_visit_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])
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

    response = client.get(f"/visits/{created['id']}", headers=other_headers)

    assert response.status_code == 403


def test_list_visits(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    _create_visit(client, user_headers, employee["id"], store["id"])
    _create_visit(
        client, user_headers, employee["id"], store["id"], visited_at="2026-01-12T09:00:00Z"
    )

    response = client.get("/visits", headers=user_headers)

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_list_visits_returns_only_owned(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )
    store = _create_store(client, admin_headers)
    _create_visit(client, user_headers, employee["id"], store["id"])
    _create_visit(client, other_headers, other_employee["id"], store["id"])

    response = client.get("/visits", headers=user_headers)

    assert response.status_code == 200
    assert {item["employee_id"] for item in response.json()} == {employee["id"]}


def test_list_visits_paginated_default_pagination(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    for i in range(3):
        _create_visit(
            client, user_headers, employee["id"], store["id"], visited_at=f"2026-01-05T09:0{i}:00Z"
        )

    response = client.get("/visits/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_visits_paginated_search_by_notes(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    _create_visit(client, user_headers, employee["id"], store["id"], notes="Stock running low")
    _create_visit(
        client,
        user_headers,
        employee["id"],
        store["id"],
        visited_at="2026-01-12T09:00:00Z",
        notes="All good",
    )

    response = client.get("/visits/paginated", headers=user_headers, params={"q": "stock"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["notes"] == "Stock running low"


def test_list_visits_paginated_filter_by_employee_id_is_ignored(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    """A caller cannot widen scope by passing a different `employee_id` filter --
    the response is still scoped to the caller's own employee (Owner Only)."""
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    other_employee = _create_employee(
        client,
        user_headers,
        employee_number="OTH-1",
        email="other.employee@example.com",
        first_name="Bob",
        last_name="Smith",
        full_name="Bob Smith",
        user_id=str(other.id),
    )
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])
    _create_visit(client, other_headers, other_employee["id"], store["id"])

    response = client.get(
        "/visits/paginated",
        headers=user_headers,
        params={"employee_id": other_employee["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == created["id"]


def test_update_visit(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])

    response = client.put(
        f"/visits/{created['id']}", json={"notes": "Updated"}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["notes"] == "Updated"


def test_update_visit_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.put(
        f"/visits/{uuid.uuid4()}", json={"notes": "Updated"}, headers=user_headers
    )

    assert response.status_code == 404


def test_update_visit_rejects_missing_employee(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])

    response = client.put(
        f"/visits/{created['id']}",
        json={"employee_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_visit_rejects_missing_store(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])

    response = client.put(
        f"/visits/{created['id']}", json={"store_id": str(uuid.uuid4())}, headers=user_headers
    )

    assert response.status_code == 404


def test_update_visit_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])
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

    response = client.put(
        f"/visits/{created['id']}", json={"notes": "Updated"}, headers=other_headers
    )

    assert response.status_code == 403


def test_delete_visit(
    client: TestClient, user: User, user_headers: dict[str, str], admin_headers: dict[str, str]
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])

    response = client.delete(f"/visits/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/visits/{created['id']}", headers=user_headers).status_code == 404


def test_delete_visit_not_found(client: TestClient, user: User, user_headers: dict[str, str]):
    _create_employee(client, user_headers, user_id=str(user.id))

    response = client.delete(f"/visits/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_delete_visit_forbidden(
    client: TestClient,
    user: User,
    user_headers: dict[str, str],
    other: User,
    other_headers: dict[str, str],
    admin_headers: dict[str, str],
):
    employee = _create_employee(client, user_headers, user_id=str(user.id))
    store = _create_store(client, admin_headers)
    created = _create_visit(client, user_headers, employee["id"], store["id"])
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

    response = client.delete(f"/visits/{created['id']}", headers=other_headers)

    assert response.status_code == 403
