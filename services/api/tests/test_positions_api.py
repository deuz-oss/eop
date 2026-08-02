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
    tables. Truncating `organizations` with CASCADE also clears `departments`
    and `positions`, since both reference `organizations` by foreign key.
    """

    async def _create() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _truncate() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE organizations, users CASCADE"))
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
    name: str = "Software Engineer",
    code: str = "SWE",
    organization_id: str,
    department_id: str,
) -> dict:
    payload = {
        "name": name,
        "code": code,
        "organization_id": organization_id,
        "department_id": department_id,
    }
    response = client.post("/positions", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_position_requires_authentication(client: TestClient):
    response = client.post(
        "/positions",
        json={
            "name": "Software Engineer",
            "code": "SWE",
            "organization_id": str(uuid.uuid4()),
            "department_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 401


def test_list_positions_requires_authentication(client: TestClient):
    response = client.get("/positions")

    assert response.status_code == 401


def test_get_position_requires_authentication(client: TestClient):
    response = client.get(f"/positions/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_position_requires_authentication(client: TestClient):
    response = client.put(f"/positions/{uuid.uuid4()}", json={"name": "New Name"})

    assert response.status_code == 401


def test_delete_position_requires_authentication(client: TestClient):
    response = client.delete(f"/positions/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_position(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])

    body = _create_position(
        client,
        user_headers,
        organization_id=organization["id"],
        department_id=department["id"],
    )

    assert body["name"] == "Software Engineer"
    assert body["code"] == "SWE"
    assert body["organization_id"] == organization["id"]
    assert body["department_id"] == department["id"]
    assert body["description"] is None
    uuid.UUID(body["id"])


def test_create_position_rejects_blank_name(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.post(
        "/positions",
        json={
            "name": "",
            "code": "SWE",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_position_rejects_missing_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.post(
        "/positions",
        json={
            "name": "Software Engineer",
            "code": "SWE",
            "organization_id": str(uuid.uuid4()),
            "department_id": department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_position_rejects_missing_department(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)

    response = client.post(
        "/positions",
        json={
            "name": "Software Engineer",
            "code": "SWE",
            "organization_id": organization["id"],
            "department_id": str(uuid.uuid4()),
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_position_rejects_department_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )

    response = client.post(
        "/positions",
        json={
            "name": "Software Engineer",
            "code": "SWE",
            "organization_id": organization["id"],
            "department_id": other_department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_position_rejects_duplicate_code_in_same_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client,
        user_headers,
        code="SWE",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.post(
        "/positions",
        json={
            "name": "Other",
            "code": "SWE",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 409


def test_create_position_allows_same_code_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    _create_position(
        client,
        user_headers,
        code="SWE",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.post(
        "/positions",
        json={
            "name": "Engineer",
            "code": "SWE",
            "organization_id": other_organization["id"],
            "department_id": other_department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 201


def test_get_position(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_position(
        client,
        user_headers,
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get(f"/positions/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Software Engineer"


def test_get_position_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/positions/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_positions(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client,
        user_headers,
        name="Software Engineer",
        code="SWE",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_position(
        client,
        user_headers,
        name="HR Manager",
        code="HRM",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get("/positions", headers=user_headers)

    assert response.status_code == 200
    names = {position["name"] for position in response.json()}
    assert {"Software Engineer", "HR Manager"}.issubset(names)


def test_list_positions_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    for i in range(3):
        _create_position(
            client,
            user_headers,
            name=f"Position {i}",
            code=f"P-{i}",
            organization_id=organization["id"],
            department_id=department["id"],
        )

    response = client.get("/positions/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_positions_paginated_custom_offset(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    for i in range(5):
        _create_position(
            client,
            user_headers,
            name=f"Position {i}",
            code=f"P-{i}",
            organization_id=organization["id"],
            department_id=department["id"],
        )

    response = client.get("/positions/paginated", headers=user_headers, params={"offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_positions_paginated_custom_limit(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    for i in range(5):
        _create_position(
            client,
            user_headers,
            name=f"Position {i}",
            code=f"P-{i}",
            organization_id=organization["id"],
            department_id=department["id"],
        )

    response = client.get("/positions/paginated", headers=user_headers, params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_positions_paginated_limit_above_maximum_is_clamped(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.get("/positions/paginated", headers=user_headers, params={"limit": 500})

    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_list_positions_paginated_negative_offset_is_rejected(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/positions/paginated", headers=user_headers, params={"offset": -1})

    assert response.status_code == 422


def test_list_positions_paginated_search_by_name(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client,
        user_headers,
        name="Software Engineer",
        code="SWE",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_position(
        client,
        user_headers,
        name="HR Manager",
        code="HRM",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get("/positions/paginated", headers=user_headers, params={"q": "software"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Software Engineer"


def test_list_positions_paginated_search_by_code(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client,
        user_headers,
        name="Engineer",
        code="SWE-ALPHA",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_position(
        client,
        user_headers,
        name="HR",
        code="HR-BETA",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get("/positions/paginated", headers=user_headers, params={"q": "alpha"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "SWE-ALPHA"


def test_list_positions_paginated_filter_by_organization_id(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    _create_position(
        client,
        user_headers,
        name="Engineer",
        code="SWE",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_position(
        client,
        user_headers,
        name="Engineer (Globex)",
        code="SWE",
        organization_id=other_organization["id"],
        department_id=other_department["id"],
    )

    response = client.get(
        "/positions/paginated",
        headers=user_headers,
        params={"organization_id": organization["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["organization_id"] == organization["id"]


def test_list_positions_paginated_filter_by_department_id(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(
        client, user_headers, name="Engineering", code="ENG", organization_id=organization["id"]
    )
    other_department = _create_department(
        client, user_headers, name="HR", code="HR", organization_id=organization["id"]
    )
    position = _create_position(
        client,
        user_headers,
        name="Engineer",
        code="SWE",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_position(
        client,
        user_headers,
        name="HR Manager",
        code="HRM",
        organization_id=organization["id"],
        department_id=other_department["id"],
    )

    response = client.get(
        "/positions/paginated", headers=user_headers, params={"department_id": department["id"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == position["id"]


def test_list_positions_paginated_no_query_returns_all(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client,
        user_headers,
        name="Engineer",
        code="SWE",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_position(
        client,
        user_headers,
        name="HR Manager",
        code="HRM",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get("/positions/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_update_position(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_position(
        client,
        user_headers,
        name="Before",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.put(
        f"/positions/{created['id']}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_position_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/positions/{uuid.uuid4()}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 404


def test_update_position_rejects_missing_department(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/positions/{created['id']}",
        json={"department_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_position_rejects_department_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    created = _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/positions/{created['id']}",
        json={"department_id": other_department["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_position_rejects_duplicate_code(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client,
        user_headers,
        code="SWE",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    other = _create_position(
        client,
        user_headers,
        name="Other",
        code="HRM",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.put(f"/positions/{other['id']}", json={"code": "SWE"}, headers=user_headers)

    assert response.status_code == 409


def test_update_position_allows_changing_organization_and_department(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    created = _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/positions/{created['id']}",
        json={
            "organization_id": other_organization["id"],
            "department_id": other_department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == other_organization["id"]
    assert body["department_id"] == other_department["id"]


def test_update_position_rejects_missing_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/positions/{created['id']}",
        json={"organization_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_position_organization_rejects_now_mismatched_existing_department(
    client: TestClient, user_headers: dict[str, str]
):
    """The effective department is always validated against the effective
    organization, even when `department_id` itself is absent from the
    request."""
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/positions/{created['id']}",
        json={"organization_id": other_organization["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_position_unrelated_field_does_not_disturb_existing_department(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/positions/{created['id']}", json={"name": "Renamed"}, headers=user_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Renamed"
    assert body["department_id"] == department["id"]


def test_delete_position(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_position(
        client,
        user_headers,
        name="To Delete",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.delete(f"/positions/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/positions/{created['id']}", headers=user_headers).status_code == 404


def test_delete_position_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/positions/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_delete_department_with_positions_fails(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    # TestClient re-raises unhandled server exceptions by default; disable that
    # here so the FK violation surfaces as the real 500 response it produces in
    # production, instead of propagating into the test as a raw exception.
    with TestClient(app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.delete(
            f"/departments/{department['id']}", headers=user_headers
        )

    assert response.status_code == 500


def test_delete_organization_with_positions_fails(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_position(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    with TestClient(app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.delete(f"/organizations/{organization['id']}")

    assert response.status_code == 500
