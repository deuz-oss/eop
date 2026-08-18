import asyncio
import uuid
from collections.abc import AsyncGenerator, Generator
from contextlib import asynccontextmanager
from typing import Annotated

import pytest
from conftest import clean_database
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.core.security import create_access_token, hash_password
from eop_api.db.engine import engine as app_engine
from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.rbac import RequireRole
from eop_api.models.user import User
from eop_api.repositories.role import RoleRepository
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

RequireAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@app.get("/protected")
async def protected(_: RequireAdmin) -> dict[str, bool]:
    return {"ok": True}


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


async def _grant_role(*, user_id: uuid.UUID, role_name: str) -> None:
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repo = RoleRepository(session)
        role = await repo.get_by_name(role_name)
        if role is None:
            role = await repo.create(name=role_name)
        await repo.assign_user(role.id, user_id)
        await session.commit()
    await engine.dispose()


@pytest.fixture
def admin_user() -> User:
    user = asyncio.run(_create_user(email="admin@example.com", password="admin-pass"))
    asyncio.run(_grant_role(user_id=user.id, role_name="admin"))
    return user


@pytest.fixture
def member_user() -> User:
    return asyncio.run(_create_user(email="member@example.com", password="member-pass"))


def test_require_role_allows_user_with_role(client: TestClient, admin_user: User):
    token = create_access_token(subject=str(admin_user.id))

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_require_role_forbids_user_without_role(client: TestClient, member_user: User):
    token = create_access_token(subject=str(member_user.id))

    response = client.get("/protected", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


def test_require_role_forbids_anonymous(client: TestClient):
    response = client.get("/protected")

    assert response.status_code in (401, 403)
