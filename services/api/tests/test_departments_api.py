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
from eop_api.repositories.user import UserRepository

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
    name: str = "Finance",
    code: str = "FIN",
    organization_id: str,
    parent_id: str | None = None,
) -> dict:
    payload: dict = {"name": name, "code": code, "organization_id": organization_id}
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/departments", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_department_requires_authentication(client: TestClient):
    response = client.post(
        "/departments",
        json={"name": "Finance", "code": "FIN", "organization_id": str(uuid.uuid4())},
    )

    assert response.status_code == 401


def test_list_departments_requires_authentication(client: TestClient):
    response = client.get("/departments")

    assert response.status_code == 401


def test_get_department_requires_authentication(client: TestClient):
    response = client.get(f"/departments/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_department_requires_authentication(client: TestClient):
    response = client.put(f"/departments/{uuid.uuid4()}", json={"name": "New Name"})

    assert response.status_code == 401


def test_delete_department_requires_authentication(client: TestClient):
    response = client.delete(f"/departments/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_department(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)

    body = _create_department(client, user_headers, organization_id=organization["id"])

    assert body["name"] == "Finance"
    assert body["code"] == "FIN"
    assert body["organization_id"] == organization["id"]
    assert body["parent_id"] is None
    uuid.UUID(body["id"])


def test_create_department_with_parent(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    parent = _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )

    child = _create_department(
        client,
        user_headers,
        name="Accounts Payable",
        code="FIN-AP",
        organization_id=organization["id"],
        parent_id=parent["id"],
    )

    assert child["parent_id"] == parent["id"]


def test_create_department_rejects_blank_name(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)

    response = client.post(
        "/departments",
        json={"name": "", "code": "FIN", "organization_id": organization["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_department_rejects_missing_organization(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.post(
        "/departments",
        json={"name": "Finance", "code": "FIN", "organization_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_department_rejects_missing_parent(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)

    response = client.post(
        "/departments",
        json={
            "name": "Accounts Payable",
            "code": "FIN-AP",
            "organization_id": organization["id"],
            "parent_id": str(uuid.uuid4()),
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_department_rejects_parent_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    parent = _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=other_organization["id"]
    )

    response = client.post(
        "/departments",
        json={
            "name": "Accounts Payable",
            "code": "FIN-AP",
            "organization_id": organization["id"],
            "parent_id": parent["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_department_rejects_duplicate_code_in_same_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    _create_department(client, user_headers, code="FIN", organization_id=organization["id"])

    response = client.post(
        "/departments",
        json={"name": "Other", "code": "FIN", "organization_id": organization["id"]},
        headers=user_headers,
    )

    assert response.status_code == 409


def test_create_department_allows_same_code_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    _create_department(client, user_headers, code="FIN", organization_id=organization["id"])

    response = client.post(
        "/departments",
        json={"name": "Finance", "code": "FIN", "organization_id": other_organization["id"]},
        headers=user_headers,
    )

    assert response.status_code == 201


def test_get_department(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    created = _create_department(
        client, user_headers, name="Finance", organization_id=organization["id"]
    )

    response = client.get(f"/departments/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Finance"


def test_get_department_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/departments/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_departments(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )
    _create_department(
        client, user_headers, name="HR", code="HR", organization_id=organization["id"]
    )

    response = client.get("/departments", headers=user_headers)

    assert response.status_code == 200
    names = {dept["name"] for dept in response.json()}
    assert {"Finance", "HR"}.issubset(names)


def test_list_departments_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    for i in range(3):
        _create_department(
            client,
            user_headers,
            name=f"Dept {i}",
            code=f"D-{i}",
            organization_id=organization["id"],
        )

    response = client.get("/departments/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_departments_paginated_custom_offset(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    for i in range(5):
        _create_department(
            client,
            user_headers,
            name=f"Dept {i}",
            code=f"D-{i}",
            organization_id=organization["id"],
        )

    response = client.get("/departments/paginated", headers=user_headers, params={"offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_departments_paginated_custom_limit(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    for i in range(5):
        _create_department(
            client,
            user_headers,
            name=f"Dept {i}",
            code=f"D-{i}",
            organization_id=organization["id"],
        )

    response = client.get("/departments/paginated", headers=user_headers, params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_departments_paginated_limit_above_maximum_is_clamped(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    _create_department(client, user_headers, organization_id=organization["id"])

    response = client.get("/departments/paginated", headers=user_headers, params={"limit": 500})

    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_list_departments_paginated_negative_offset_is_rejected(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/departments/paginated", headers=user_headers, params={"offset": -1})

    assert response.status_code == 422


def test_list_departments_paginated_search_by_name(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    _create_department(
        client,
        user_headers,
        name="Finance Department",
        code="FIN",
        organization_id=organization["id"],
    )
    _create_department(
        client, user_headers, name="Human Resources", code="HR", organization_id=organization["id"]
    )

    response = client.get("/departments/paginated", headers=user_headers, params={"q": "finance"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Finance Department"


def test_list_departments_paginated_search_by_code(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    _create_department(
        client, user_headers, name="Finance", code="FIN-ALPHA", organization_id=organization["id"]
    )
    _create_department(
        client, user_headers, name="HR", code="HR-BETA", organization_id=organization["id"]
    )

    response = client.get("/departments/paginated", headers=user_headers, params={"q": "alpha"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "FIN-ALPHA"


def test_list_departments_paginated_filter_by_organization_id(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )
    _create_department(
        client,
        user_headers,
        name="Finance (Globex)",
        code="FIN",
        organization_id=other_organization["id"],
    )

    response = client.get(
        "/departments/paginated",
        headers=user_headers,
        params={"organization_id": organization["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["organization_id"] == organization["id"]


def test_list_departments_paginated_filter_by_parent_id(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    parent = _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )
    child = _create_department(
        client,
        user_headers,
        name="Accounts Payable",
        code="FIN-AP",
        organization_id=organization["id"],
        parent_id=parent["id"],
    )
    _create_department(
        client, user_headers, name="HR", code="HR", organization_id=organization["id"]
    )

    response = client.get(
        "/departments/paginated", headers=user_headers, params={"parent_id": parent["id"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == child["id"]


def test_list_departments_paginated_no_query_returns_all(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )
    _create_department(
        client, user_headers, name="HR", code="HR", organization_id=organization["id"]
    )

    response = client.get("/departments/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_update_department(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    created = _create_department(
        client, user_headers, name="Before", organization_id=organization["id"]
    )

    response = client.put(
        f"/departments/{created['id']}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_department_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(
        f"/departments/{uuid.uuid4()}", json={"name": "After"}, headers=user_headers
    )

    assert response.status_code == 404


def test_update_department_rejects_missing_parent(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    created = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.put(
        f"/departments/{created['id']}",
        json={"parent_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_department_rejects_parent_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    created = _create_department(client, user_headers, organization_id=organization["id"])
    other_parent = _create_department(
        client, user_headers, name="Finance (Globex)", organization_id=other_organization["id"]
    )

    response = client.put(
        f"/departments/{created['id']}",
        json={"parent_id": other_parent["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_department_rejects_self_parent(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    created = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.put(
        f"/departments/{created['id']}",
        json={"parent_id": created["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_department_rejects_duplicate_code(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    _create_department(client, user_headers, code="FIN", organization_id=organization["id"])
    other = _create_department(
        client, user_headers, name="Other", code="HR", organization_id=organization["id"]
    )

    response = client.put(f"/departments/{other['id']}", json={"code": "FIN"}, headers=user_headers)

    assert response.status_code == 409


def test_update_department_allows_changing_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    created = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.put(
        f"/departments/{created['id']}",
        json={"organization_id": other_organization["id"]},
        headers=user_headers,
    )

    assert response.status_code == 200
    assert response.json()["organization_id"] == other_organization["id"]


def test_update_department_rejects_missing_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    created = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.put(
        f"/departments/{created['id']}",
        json={"organization_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_department_organization_accepts_parent_in_new_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    parent = _create_department(
        client, user_headers, name="Finance (Globex)", organization_id=other_organization["id"]
    )
    created = _create_department(
        client,
        user_headers,
        name="Accounts Payable",
        code="FIN-AP",
        organization_id=organization["id"],
    )

    response = client.put(
        f"/departments/{created['id']}",
        json={"organization_id": other_organization["id"], "parent_id": parent["id"]},
        headers=user_headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["organization_id"] == other_organization["id"]
    assert body["parent_id"] == parent["id"]


def test_update_department_organization_rejects_parent_not_in_new_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    parent = _create_department(
        client, user_headers, name="Finance", organization_id=organization["id"]
    )
    created = _create_department(
        client,
        user_headers,
        name="Accounts Payable",
        code="FIN-AP",
        organization_id=organization["id"],
    )

    response = client.put(
        f"/departments/{created['id']}",
        json={"organization_id": other_organization["id"], "parent_id": parent["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_department_organization_rejects_duplicate_code_in_new_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    _create_department(client, user_headers, code="OPS", organization_id=other_organization["id"])
    created = _create_department(
        client,
        user_headers,
        name="Operations (Acme)",
        code="OPS",
        organization_id=organization["id"],
    )

    response = client.put(
        f"/departments/{created['id']}",
        json={"organization_id": other_organization["id"]},
        headers=user_headers,
    )

    assert response.status_code == 409


def test_update_department_organization_rejects_now_mismatched_existing_parent(
    client: TestClient, user_headers: dict[str, str]
):
    """The effective parent is always validated against the effective
    organization, even when `parent_id` itself is absent from the request."""
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    parent = _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )
    child = _create_department(
        client,
        user_headers,
        name="Accounts Payable",
        code="FIN-AP",
        organization_id=organization["id"],
        parent_id=parent["id"],
    )

    response = client.put(
        f"/departments/{child['id']}",
        json={"organization_id": other_organization["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_department_unrelated_field_does_not_disturb_existing_parent(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    parent = _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )
    child = _create_department(
        client,
        user_headers,
        name="Accounts Payable",
        code="FIN-AP",
        organization_id=organization["id"],
        parent_id=parent["id"],
    )

    response = client.put(
        f"/departments/{child['id']}", json={"name": "AP Renamed"}, headers=user_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "AP Renamed"
    assert body["parent_id"] == parent["id"]


def test_update_department_organization_does_not_move_children(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    parent = _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )
    child = _create_department(
        client,
        user_headers,
        name="Accounts Payable",
        code="FIN-AP",
        organization_id=organization["id"],
        parent_id=parent["id"],
    )

    response = client.put(
        f"/departments/{parent['id']}",
        json={"organization_id": other_organization["id"]},
        headers=user_headers,
    )
    assert response.status_code == 200

    unchanged_child = client.get(f"/departments/{child['id']}", headers=user_headers).json()
    assert unchanged_child["organization_id"] == organization["id"]
    assert unchanged_child["parent_id"] == parent["id"]


def test_delete_department(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    created = _create_department(
        client, user_headers, name="To Delete", organization_id=organization["id"]
    )

    response = client.delete(f"/departments/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/departments/{created['id']}", headers=user_headers).status_code == 404


def test_delete_department_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/departments/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_delete_department_with_children_fails(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    parent = _create_department(
        client, user_headers, name="Finance", code="FIN", organization_id=organization["id"]
    )
    _create_department(
        client,
        user_headers,
        name="Accounts Payable",
        code="FIN-AP",
        organization_id=organization["id"],
        parent_id=parent["id"],
    )

    # TestClient re-raises unhandled server exceptions by default; disable that
    # here so the FK violation surfaces as the real 500 response it produces in
    # production, instead of propagating into the test as a raw exception.
    with TestClient(app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.delete(f"/departments/{parent['id']}", headers=user_headers)

    assert response.status_code == 500
