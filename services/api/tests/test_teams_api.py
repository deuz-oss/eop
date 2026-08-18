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


def _create_team(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Backend Team",
    code: str = "BACKEND",
    organization_id: str,
    department_id: str,
    parent_id: str | None = None,
) -> dict:
    payload: dict = {
        "name": name,
        "code": code,
        "organization_id": organization_id,
        "department_id": department_id,
    }
    if parent_id is not None:
        payload["parent_id"] = parent_id
    response = client.post("/teams", json=payload, headers=headers)
    assert response.status_code == 201
    return response.json()


def test_create_team_requires_authentication(client: TestClient):
    response = client.post(
        "/teams",
        json={
            "name": "Backend Team",
            "code": "BACKEND",
            "organization_id": str(uuid.uuid4()),
            "department_id": str(uuid.uuid4()),
        },
    )

    assert response.status_code == 401


def test_list_teams_requires_authentication(client: TestClient):
    response = client.get("/teams")

    assert response.status_code == 401


def test_get_team_requires_authentication(client: TestClient):
    response = client.get(f"/teams/{uuid.uuid4()}")

    assert response.status_code == 401


def test_update_team_requires_authentication(client: TestClient):
    response = client.put(f"/teams/{uuid.uuid4()}", json={"name": "New Name"})

    assert response.status_code == 401


def test_delete_team_requires_authentication(client: TestClient):
    response = client.delete(f"/teams/{uuid.uuid4()}")

    assert response.status_code == 401


def test_create_team(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])

    body = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    assert body["name"] == "Backend Team"
    assert body["code"] == "BACKEND"
    assert body["organization_id"] == organization["id"]
    assert body["department_id"] == department["id"]
    assert body["parent_id"] is None
    uuid.UUID(body["id"])


def test_create_team_with_parent(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    parent = _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    child = _create_team(
        client,
        user_headers,
        name="API Squad",
        code="API",
        organization_id=organization["id"],
        department_id=department["id"],
        parent_id=parent["id"],
    )

    assert child["parent_id"] == parent["id"]


def test_create_team_rejects_blank_name(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.post(
        "/teams",
        json={
            "name": "",
            "code": "BACKEND",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_team_rejects_missing_organization(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.post(
        "/teams",
        json={
            "name": "Backend Team",
            "code": "BACKEND",
            "organization_id": str(uuid.uuid4()),
            "department_id": department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_team_rejects_missing_department(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)

    response = client.post(
        "/teams",
        json={
            "name": "Backend Team",
            "code": "BACKEND",
            "organization_id": organization["id"],
            "department_id": str(uuid.uuid4()),
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_team_rejects_department_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )

    response = client.post(
        "/teams",
        json={
            "name": "Backend Team",
            "code": "BACKEND",
            "organization_id": organization["id"],
            "department_id": other_department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_team_rejects_missing_parent(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])

    response = client.post(
        "/teams",
        json={
            "name": "API Squad",
            "code": "API",
            "organization_id": organization["id"],
            "department_id": department["id"],
            "parent_id": str(uuid.uuid4()),
        },
        headers=user_headers,
    )

    assert response.status_code == 404


def test_create_team_rejects_parent_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    parent = _create_team(
        client,
        user_headers,
        name="Backend (Globex)",
        code="BACKEND",
        organization_id=other_organization["id"],
        department_id=other_department["id"],
    )

    response = client.post(
        "/teams",
        json={
            "name": "API Squad",
            "code": "API",
            "organization_id": organization["id"],
            "department_id": department["id"],
            "parent_id": parent["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_team_rejects_parent_in_different_department(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(
        client, user_headers, name="Engineering", code="ENG", organization_id=organization["id"]
    )
    other_department = _create_department(
        client, user_headers, name="HR", code="HR", organization_id=organization["id"]
    )
    parent = _create_team(
        client,
        user_headers,
        name="HR Ops",
        code="HR-OPS",
        organization_id=organization["id"],
        department_id=other_department["id"],
    )

    response = client.post(
        "/teams",
        json={
            "name": "API Squad",
            "code": "API",
            "organization_id": organization["id"],
            "department_id": department["id"],
            "parent_id": parent["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 422


def test_create_team_rejects_duplicate_code_in_same_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_team(
        client,
        user_headers,
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.post(
        "/teams",
        json={
            "name": "Other",
            "code": "BACKEND",
            "organization_id": organization["id"],
            "department_id": department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 409


def test_create_team_allows_same_code_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    _create_team(
        client,
        user_headers,
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.post(
        "/teams",
        json={
            "name": "Backend (Globex)",
            "code": "BACKEND",
            "organization_id": other_organization["id"],
            "department_id": other_department["id"],
        },
        headers=user_headers,
    )

    assert response.status_code == 201


def test_get_team(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.get(f"/teams/{created['id']}", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Backend Team"


def test_get_team_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.get(f"/teams/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_list_teams(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_team(
        client,
        user_headers,
        name="Frontend Team",
        code="FRONTEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get("/teams", headers=user_headers)

    assert response.status_code == 200
    names = {team["name"] for team in response.json()}
    assert {"Backend Team", "Frontend Team"}.issubset(names)


def test_list_teams_paginated_default_pagination(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    for i in range(3):
        _create_team(
            client,
            user_headers,
            name=f"Team {i}",
            code=f"T-{i}",
            organization_id=organization["id"],
            department_id=department["id"],
        )

    response = client.get("/teams/paginated", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_teams_paginated_custom_offset(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    for i in range(5):
        _create_team(
            client,
            user_headers,
            name=f"Team {i}",
            code=f"T-{i}",
            organization_id=organization["id"],
            department_id=department["id"],
        )

    response = client.get("/teams/paginated", headers=user_headers, params={"offset": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 3


def test_list_teams_paginated_custom_limit(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    for i in range(5):
        _create_team(
            client,
            user_headers,
            name=f"Team {i}",
            code=f"T-{i}",
            organization_id=organization["id"],
            department_id=department["id"],
        )

    response = client.get("/teams/paginated", headers=user_headers, params={"limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_teams_paginated_limit_above_maximum_is_clamped(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.get("/teams/paginated", headers=user_headers, params={"limit": 500})

    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_list_teams_paginated_negative_offset_is_rejected(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/teams/paginated", headers=user_headers, params={"offset": -1})

    assert response.status_code == 422


def test_list_teams_paginated_search_by_name(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_team(
        client,
        user_headers,
        name="Frontend Team",
        code="FRONTEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get("/teams/paginated", headers=user_headers, params={"q": "backend"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Backend Team"


def test_list_teams_paginated_search_by_code(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BE-ALPHA",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_team(
        client,
        user_headers,
        name="Frontend Team",
        code="FE-BETA",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get("/teams/paginated", headers=user_headers, params={"q": "alpha"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["code"] == "BE-ALPHA"


def test_list_teams_paginated_filter_by_organization_id(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_team(
        client,
        user_headers,
        name="Backend (Globex)",
        code="BACKEND",
        organization_id=other_organization["id"],
        department_id=other_department["id"],
    )

    response = client.get(
        "/teams/paginated",
        headers=user_headers,
        params={"organization_id": organization["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["organization_id"] == organization["id"]


def test_list_teams_paginated_filter_by_department_id(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(
        client, user_headers, name="Engineering", code="ENG", organization_id=organization["id"]
    )
    other_department = _create_department(
        client, user_headers, name="HR", code="HR", organization_id=organization["id"]
    )
    _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_team(
        client,
        user_headers,
        name="HR Ops",
        code="HR-OPS",
        organization_id=organization["id"],
        department_id=other_department["id"],
    )

    response = client.get(
        "/teams/paginated",
        headers=user_headers,
        params={"department_id": department["id"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["department_id"] == department["id"]


def test_list_teams_paginated_filter_by_parent_id(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    parent = _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    child = _create_team(
        client,
        user_headers,
        name="API Squad",
        code="API",
        organization_id=organization["id"],
        department_id=department["id"],
        parent_id=parent["id"],
    )
    _create_team(
        client,
        user_headers,
        name="Frontend Team",
        code="FRONTEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get(
        "/teams/paginated", headers=user_headers, params={"parent_id": parent["id"]}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == child["id"]


def test_list_teams_paginated_no_query_returns_all(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_team(
        client,
        user_headers,
        name="Frontend Team",
        code="FRONTEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.get("/teams/paginated", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2


def test_update_team(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_team(
        client,
        user_headers,
        name="Before",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.put(f"/teams/{created['id']}", json={"name": "After"}, headers=user_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "After"


def test_update_team_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.put(f"/teams/{uuid.uuid4()}", json={"name": "After"}, headers=user_headers)

    assert response.status_code == 404


def test_update_team_rejects_missing_department(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/teams/{created['id']}",
        json={"department_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_team_rejects_department_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/teams/{created['id']}",
        json={"department_id": other_department["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_team_rejects_missing_parent(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/teams/{created['id']}",
        json={"parent_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_team_rejects_parent_in_different_organization(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )
    other_parent = _create_team(
        client,
        user_headers,
        name="Backend (Globex)",
        code="BACKEND-G",
        organization_id=other_organization["id"],
        department_id=other_department["id"],
    )

    response = client.put(
        f"/teams/{created['id']}",
        json={"parent_id": other_parent["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_team_rejects_parent_in_different_department(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(
        client, user_headers, name="Engineering", code="ENG", organization_id=organization["id"]
    )
    other_department = _create_department(
        client, user_headers, name="HR", code="HR", organization_id=organization["id"]
    )
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )
    other_parent = _create_team(
        client,
        user_headers,
        name="HR Ops",
        code="HR-OPS",
        organization_id=organization["id"],
        department_id=other_department["id"],
    )

    response = client.put(
        f"/teams/{created['id']}",
        json={"parent_id": other_parent["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_team_rejects_self_parent(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/teams/{created['id']}",
        json={"parent_id": created["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_team_rejects_duplicate_code(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    _create_team(
        client,
        user_headers,
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    other = _create_team(
        client,
        user_headers,
        name="Other",
        code="FRONTEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.put(f"/teams/{other['id']}", json={"code": "BACKEND"}, headers=user_headers)

    assert response.status_code == 409


def test_update_team_allows_changing_organization_and_department(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/teams/{created['id']}",
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


def test_update_team_rejects_missing_organization(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/teams/{created['id']}",
        json={"organization_id": str(uuid.uuid4())},
        headers=user_headers,
    )

    assert response.status_code == 404


def test_update_team_organization_rejects_now_mismatched_department(
    client: TestClient, user_headers: dict[str, str]
):
    """The effective department is always validated against the effective
    organization, even when `department_id` itself is absent from the
    request."""
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_team(
        client, user_headers, organization_id=organization["id"], department_id=department["id"]
    )

    response = client.put(
        f"/teams/{created['id']}",
        json={"organization_id": other_organization["id"]},
        headers=user_headers,
    )

    assert response.status_code == 422


def test_update_team_unrelated_field_does_not_disturb_existing_parent(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    parent = _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    child = _create_team(
        client,
        user_headers,
        name="API Squad",
        code="API",
        organization_id=organization["id"],
        department_id=department["id"],
        parent_id=parent["id"],
    )

    response = client.put(
        f"/teams/{child['id']}", json={"name": "API Squad Renamed"}, headers=user_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "API Squad Renamed"
    assert body["parent_id"] == parent["id"]


def test_update_team_organization_does_not_move_children(
    client: TestClient, user_headers: dict[str, str]
):
    organization = _create_organization(client, user_headers, name="Acme Corp")
    other_organization = _create_organization(client, user_headers, name="Globex Corp")
    department = _create_department(client, user_headers, organization_id=organization["id"])
    other_department = _create_department(
        client, user_headers, organization_id=other_organization["id"]
    )
    parent = _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    child = _create_team(
        client,
        user_headers,
        name="API Squad",
        code="API",
        organization_id=organization["id"],
        department_id=department["id"],
        parent_id=parent["id"],
    )

    response = client.put(
        f"/teams/{parent['id']}",
        json={
            "organization_id": other_organization["id"],
            "department_id": other_department["id"],
        },
        headers=user_headers,
    )
    assert response.status_code == 200

    unchanged_child = client.get(f"/teams/{child['id']}", headers=user_headers).json()
    assert unchanged_child["organization_id"] == organization["id"]
    assert unchanged_child["department_id"] == department["id"]
    assert unchanged_child["parent_id"] == parent["id"]


def test_delete_team(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    created = _create_team(
        client,
        user_headers,
        name="To Delete",
        organization_id=organization["id"],
        department_id=department["id"],
    )

    response = client.delete(f"/teams/{created['id']}", headers=user_headers)

    assert response.status_code == 204
    assert client.get(f"/teams/{created['id']}", headers=user_headers).status_code == 404


def test_delete_team_not_found(client: TestClient, user_headers: dict[str, str]):
    response = client.delete(f"/teams/{uuid.uuid4()}", headers=user_headers)

    assert response.status_code == 404


def test_delete_team_with_children_fails(client: TestClient, user_headers: dict[str, str]):
    organization = _create_organization(client, user_headers)
    department = _create_department(client, user_headers, organization_id=organization["id"])
    parent = _create_team(
        client,
        user_headers,
        name="Backend Team",
        code="BACKEND",
        organization_id=organization["id"],
        department_id=department["id"],
    )
    _create_team(
        client,
        user_headers,
        name="API Squad",
        code="API",
        organization_id=organization["id"],
        department_id=department["id"],
        parent_id=parent["id"],
    )

    # TestClient re-raises unhandled server exceptions by default; disable that
    # here so the FK violation surfaces as the real 500 response it produces in
    # production, instead of propagating into the test as a raw exception.
    with TestClient(app, raise_server_exceptions=False) as non_raising_client:
        response = non_raising_client.delete(f"/teams/{parent['id']}", headers=user_headers)

    assert response.status_code == 500
