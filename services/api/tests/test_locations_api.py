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

# Location Authorization: reads remain open to any authenticated user;
# create/update/delete are Role Based (`RequireRole("admin")`), mirroring
# `test_stores_api.py`'s exact fixture/test pattern.


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


def _create_location_type(
    client: TestClient, headers: dict[str, str], *, code: str = "store", name: str = "Store"
) -> dict:
    response = client.post("/location-types", json={"code": code, "name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()


def _create_location(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Headquarters",
    code: str = "HQ-1",
    location_type_id: str,
    parent_id: str | None = None,
) -> dict:
    payload: dict = {"name": name, "code": code, "location_type_id": location_type_id}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/locations", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


# --- authentication -----------------------------------------------------------


def test_create_location_requires_authentication(client: TestClient):
    response = client.post(
        "/locations",
        json={"name": "Headquarters", "code": "HQ-1", "location_type_id": str(uuid.uuid4())},
    )

    assert response.status_code == 401


def test_list_locations_requires_authentication(client: TestClient):
    response = client.get("/locations")

    assert response.status_code == 401


def test_get_location_requires_authentication(client: TestClient):
    response = client.get(f"/locations/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_location_requires_authentication(client: TestClient):
    response = client.put(f"/locations/{uuid.uuid4()}", json={"name": "New Name"})

    assert response.status_code == 401


def test_delete_location_requires_authentication(client: TestClient):
    response = client.delete(f"/locations/{uuid.uuid4()}")

    assert response.status_code == 401


# --- authorization: reads open to any authenticated user, writes admin-only ---


def test_list_locations_allows_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.get("/locations", headers=user_headers)

    assert response.status_code == 200


def test_get_location_allows_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/locations/{uuid.uuid4()}", headers=user_headers)

    # 404 (not 403) proves the request reached the service layer -- the
    # non-admin caller was not rejected by authorization.
    assert response.status_code == 404


def test_list_locations_allows_admin(client: TestClient, admin_headers: dict[str, str]):
    response = client.get("/locations", headers=admin_headers)

    assert response.status_code == 200


def test_create_location_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.post(
        "/locations",
        json={"name": "Headquarters", "code": "HQ-1", "location_type_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 403


def test_update_location_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/locations/{uuid.uuid4()}", json={"name": "New Name"}, headers=user_headers
    )

    assert response.status_code == 403


def test_delete_location_rejects_non_admin(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/locations/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 403


# --- create ---------------------------------------------------------------


def test_create_location(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)

    body = _create_location(client, admin_headers, location_type_id=location_type["id"])

    assert body["name"] == "Headquarters"
    assert body["code"] == "HQ-1"
    assert body["location_type_id"] == location_type["id"]
    assert body["parent_id"] is None
    uuid.UUID(body["id"])


def test_create_location_with_parent(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)
    parent = _create_location(
        client,
        admin_headers,
        name="Headquarters",
        code="HQ-1",
        location_type_id=location_type["id"],
    )

    child = _create_location(
        client,
        admin_headers,
        name="Region A",
        code="REG-A",
        location_type_id=location_type["id"],
        parent_id=parent["id"],
    )

    assert child["parent_id"] == parent["id"]


def test_create_location_rejects_blank_name(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)

    response = client.post(
        "/locations",
        json={"name": "", "code": "HQ-1", "location_type_id": location_type["id"]},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_location_rejects_missing_location_type(
    client: TestClient, admin_headers: dict[str, str]
):
    response = client.post(
        "/locations",
        json={"name": "Headquarters", "code": "HQ-1", "location_type_id": str(uuid.uuid4())},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_create_location_rejects_missing_parent(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)

    response = client.post(
        "/locations",
        json={
            "name": "Region A",
            "code": "REG-A",
            "location_type_id": location_type["id"],
            "parent_id": str(uuid.uuid4()),
        },
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_create_location_rejects_duplicate_code(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)
    _create_location(client, admin_headers, code="HQ-1", location_type_id=location_type["id"])

    response = client.post(
        "/locations",
        json={"name": "Other", "code": "HQ-1", "location_type_id": location_type["id"]},
        headers=admin_headers,
    )

    assert response.status_code == 409


# --- read -------------------------------------------------------------------


def test_get_location(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    created = _create_location(
        client, admin_headers, name="Globex", location_type_id=location_type["id"]
    )

    response = client.get(f"/locations/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Globex"


def test_get_location_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/locations/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_locations(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    _create_location(
        client, admin_headers, name="Alpha", code="A-1", location_type_id=location_type["id"]
    )
    _create_location(
        client, admin_headers, name="Beta", code="B-1", location_type_id=location_type["id"]
    )

    response = client.get("/locations", headers=user_headers)

    assert response.status_code == 200
    names = {loc["name"] for loc in response.json()}
    assert {"Alpha", "Beta"}.issubset(names)


def test_list_locations_paginated_default_pagination(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    for i in range(3):
        _create_location(
            client,
            admin_headers,
            name=f"Store {i}",
            code=f"S-{i}",
            location_type_id=location_type["id"],
        )

    response = client.get("/locations/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_locations_paginated_custom_offset(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    for i in range(5):
        _create_location(
            client,
            admin_headers,
            name=f"Store {i}",
            code=f"S-{i}",
            location_type_id=location_type["id"],
        )

    response = client.get("/locations/paginated", headers=user_headers, params={"offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_locations_paginated_custom_limit(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    for i in range(5):
        _create_location(
            client,
            admin_headers,
            name=f"Store {i}",
            code=f"S-{i}",
            location_type_id=location_type["id"],
        )

    response = client.get("/locations/paginated", headers=user_headers, params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_locations_paginated_limit_above_maximum_is_clamped(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    _create_location(client, admin_headers, location_type_id=location_type["id"])

    response = client.get("/locations/paginated", headers=user_headers, params={"limit": 500})

    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_list_locations_paginated_negative_offset_is_rejected(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/locations/paginated", headers=user_headers, params={"offset": -1})

    assert response.status_code == 422


def test_list_locations_paginated_search_by_name(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    _create_location(
        client,
        admin_headers,
        name="Open Warehouse",
        code="W-1",
        location_type_id=location_type["id"],
    )
    _create_location(
        client, admin_headers, name="Closed Store", code="S-1", location_type_id=location_type["id"]
    )

    response = client.get("/locations/paginated", headers=user_headers, params={"q": "open"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Open Warehouse"


def test_list_locations_paginated_search_by_code(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    _create_location(
        client,
        admin_headers,
        name="Warehouse",
        code="WH-ALPHA",
        location_type_id=location_type["id"],
    )
    _create_location(
        client, admin_headers, name="Store", code="ST-BETA", location_type_id=location_type["id"]
    )

    response = client.get("/locations/paginated", headers=user_headers, params={"q": "alpha"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "WH-ALPHA"


def test_list_locations_paginated_filter_by_location_type_id(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    warehouse = _create_location_type(client, admin_headers, code="warehouse", name="Warehouse")
    store = _create_location_type(client, admin_headers, code="store", name="Store")
    _create_location(
        client, admin_headers, name="Main Warehouse", code="W-1", location_type_id=warehouse["id"]
    )
    _create_location(
        client, admin_headers, name="Main Store", code="S-1", location_type_id=store["id"]
    )

    response = client.get(
        "/locations/paginated", headers=user_headers, params={"location_type_id": warehouse["id"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["location_type_id"] == warehouse["id"]


def test_list_locations_paginated_no_query_returns_all(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    _create_location(
        client, admin_headers, name="Alpha", code="A-1", location_type_id=location_type["id"]
    )
    _create_location(
        client, admin_headers, name="Beta", code="B-1", location_type_id=location_type["id"]
    )

    response = client.get("/locations/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


# --- update -------------------------------------------------------------------


def test_update_location(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)
    created = _create_location(
        client, admin_headers, name="Before", location_type_id=location_type["id"]
    )

    response = client.put(
        f"/locations/{created['id']}", json={"name": "After"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_location_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.put(
        f"/locations/{uuid.uuid4()}", json={"name": "After"}, headers=admin_headers
    )

    assert response.status_code == 404


def test_update_location_rejects_missing_parent(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)
    created = _create_location(client, admin_headers, location_type_id=location_type["id"])

    response = client.put(
        f"/locations/{created['id']}",
        json={"parent_id": str(uuid.uuid4())},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_location_rejects_self_parent(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)
    created = _create_location(client, admin_headers, location_type_id=location_type["id"])

    response = client.put(
        f"/locations/{created['id']}",
        json={"parent_id": created["id"]},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_update_location_rejects_missing_location_type(
    client: TestClient, admin_headers: dict[str, str]
):
    location_type = _create_location_type(client, admin_headers)
    created = _create_location(client, admin_headers, location_type_id=location_type["id"])

    response = client.put(
        f"/locations/{created['id']}",
        json={"location_type_id": str(uuid.uuid4())},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_location_rejects_duplicate_code(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)
    _create_location(client, admin_headers, code="HQ-1", location_type_id=location_type["id"])
    other = _create_location(
        client, admin_headers, name="Other", code="HQ-2", location_type_id=location_type["id"]
    )

    response = client.put(f"/locations/{other['id']}", json={"code": "HQ-1"}, headers=admin_headers)

    assert response.status_code == 409


# --- delete -------------------------------------------------------------------


def test_delete_location(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)
    created = _create_location(
        client, admin_headers, name="To Delete", location_type_id=location_type["id"]
    )

    response = client.delete(f"/locations/{created['id']}", headers=admin_headers)

    assert response.status_code == 204
    assert client.get(f"/locations/{created['id']}", headers=admin_headers).status_code == 404


def test_delete_location_not_found(client: TestClient, admin_headers: dict[str, str]):
    response = client.delete(f"/locations/{uuid.uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_delete_location_with_children_fails(client: TestClient, admin_headers: dict[str, str]):
    location_type = _create_location_type(client, admin_headers)
    parent = _create_location(
        client,
        admin_headers,
        name="Headquarters",
        code="HQ-1",
        location_type_id=location_type["id"],
    )
    _create_location(
        client,
        admin_headers,
        name="Region A",
        code="REG-A",
        location_type_id=location_type["id"],
        parent_id=parent["id"],
    )

    # TestClient re-raises unhandled server exceptions by default; disable that
    # here so the FK violation surfaces as the real 500 response it produces in
    # production, instead of propagating into the test as a raw exception.
    with TestClient(app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.delete(f"/locations/{parent['id']}", headers=admin_headers)

    assert response.status_code == 500
