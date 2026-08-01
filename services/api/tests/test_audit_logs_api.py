import asyncio
import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.audit import AuditAction, AuditEntityType
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.audit_log import AuditLogRepository
from eop_api.repositories.user import UserRepository


@pytest.fixture(autouse=True)
def _tables() -> Generator[None]:
    """Ensures all tables exist and are empty for each test.

    The API runs against the real app and its real (default) database engine,
    so state is reset via TRUNCATE rather than dropping the migration-managed
    tables.
    """

    async def _create() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    async def _truncate() -> None:
        engine = create_async_engine(settings.database_url)
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE audit_logs, users CASCADE"))
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


async def _seed_audit_log(*, action: AuditAction, entity_type: AuditEntityType) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        await AuditLogRepository(session).create(
            user_id=None,
            action=action.value,
            entity_type=entity_type.value,
            entity_id=uuid.uuid4(),
        )
        await session.commit()
    await engine.dispose()


def seed_audit_log(
    *,
    action: AuditAction = AuditAction.CREATE,
    entity_type: AuditEntityType = AuditEntityType.ORGANIZATION,
) -> None:
    asyncio.run(_seed_audit_log(action=action, entity_type=entity_type))


def test_list_audit_logs_requires_authentication(client: TestClient):
    response = client.get("/audit-logs")

    assert response.status_code == 401


def test_list_audit_logs_returns_200_for_authenticated_user(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/audit-logs", headers=user_headers)

    assert response.status_code == 200


def test_list_audit_logs_returns_seeded_entries(client: TestClient, user_headers: dict[str, str]):
    seed_audit_log(action=AuditAction.CREATE, entity_type=AuditEntityType.ORGANIZATION)
    seed_audit_log(action=AuditAction.DELETE, entity_type=AuditEntityType.PROJECT)

    response = client.get("/audit-logs", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    entity_types = {item["entity_type"] for item in body["items"]}
    assert entity_types == {"organization", "project"}


def test_list_audit_logs_paginated_default_pagination(
    client: TestClient, user_headers: dict[str, str]
):
    for _i in range(3):
        seed_audit_log()

    response = client.get("/audit-logs", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 0
    assert body["limit"] == 50
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_audit_logs_paginated_custom_offset_and_limit(
    client: TestClient, user_headers: dict[str, str]
):
    for _i in range(5):
        seed_audit_log()

    response = client.get("/audit-logs", headers=user_headers, params={"offset": 2, "limit": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["offset"] == 2
    assert body["limit"] == 2
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_audit_logs_paginated_limit_above_maximum_is_clamped(
    client: TestClient, user_headers: dict[str, str]
):
    seed_audit_log()

    response = client.get("/audit-logs", headers=user_headers, params={"limit": 500})

    assert response.status_code == 200
    assert response.json()["limit"] == 100


def test_list_audit_logs_paginated_negative_offset_is_rejected(
    client: TestClient, user_headers: dict[str, str]
):
    response = client.get("/audit-logs", headers=user_headers, params={"offset": -1})

    assert response.status_code == 422


def test_list_audit_logs_search_by_entity_type(client: TestClient, user_headers: dict[str, str]):
    seed_audit_log(action=AuditAction.CREATE, entity_type=AuditEntityType.ORGANIZATION)
    seed_audit_log(action=AuditAction.CREATE, entity_type=AuditEntityType.PROJECT)

    response = client.get("/audit-logs", headers=user_headers, params={"q": "organization"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["entity_type"] == "organization"


def test_list_audit_logs_search_by_action(client: TestClient, user_headers: dict[str, str]):
    seed_audit_log(action=AuditAction.CREATE, entity_type=AuditEntityType.ORGANIZATION)
    seed_audit_log(action=AuditAction.DELETE, entity_type=AuditEntityType.ORGANIZATION)

    response = client.get("/audit-logs", headers=user_headers, params={"q": "delete"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["action"] == "delete"


def test_list_audit_logs_no_query_returns_all(client: TestClient, user_headers: dict[str, str]):
    seed_audit_log(action=AuditAction.CREATE, entity_type=AuditEntityType.ORGANIZATION)
    seed_audit_log(action=AuditAction.DELETE, entity_type=AuditEntityType.PROJECT)

    response = client.get("/audit-logs", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["total"] == 2
