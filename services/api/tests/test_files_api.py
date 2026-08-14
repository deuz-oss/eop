import asyncio
import io
from collections.abc import AsyncIterator, Generator
from typing import BinaryIO

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.api.files import get_file_service
from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.db.base import Base
from eop_api.main import app
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository
from eop_api.services.file import FileService
from eop_api.storage.base import StorageProvider
from eop_api.storage.exceptions import StorageObjectNotFoundError


class FakeStorageProvider(StorageProvider):
    """In-memory `StorageProvider` test double -- no real MinIO involved."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    async def upload(
        self, *, bucket: str, key: str, data: BinaryIO, length: int, content_type: str
    ) -> None:
        self.objects[(bucket, key)] = data.read()

    async def download(self, *, bucket: str, key: str) -> AsyncIterator[bytes]:
        if (bucket, key) not in self.objects:
            raise StorageObjectNotFoundError(key)
        content = self.objects[(bucket, key)]

        async def _stream() -> AsyncIterator[bytes]:
            yield content

        return _stream()

    async def delete(self, *, bucket: str, key: str) -> None:
        self.objects.pop((bucket, key), None)

    async def exists(self, *, bucket: str, key: str) -> bool:
        return (bucket, key) in self.objects


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
            await conn.execute(text("TRUNCATE TABLE file_objects, users CASCADE"))
        await engine.dispose()

    asyncio.run(_create())
    yield
    asyncio.run(_truncate())


@pytest.fixture
def fake_storage() -> FakeStorageProvider:
    return FakeStorageProvider()


@pytest.fixture(autouse=True)
def _override_file_service(fake_storage: FakeStorageProvider) -> Generator[None]:
    """Routes the API through a fake storage provider instead of real MinIO."""
    app.dependency_overrides[get_file_service] = lambda: FileService(storage=fake_storage)
    yield
    app.dependency_overrides.pop(get_file_service, None)


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


def _upload(
    client: TestClient,
    headers: dict[str, str],
    *,
    filename: str = "report.pdf",
    content: bytes = b"hello world",
    content_type: str = "application/pdf",
):
    return client.post(
        "/files",
        headers=headers,
        files={"file": (filename, io.BytesIO(content), content_type)},
    )


# --- authentication ---------------------------------------------------------


def test_upload_requires_authentication(client: TestClient):
    response = client.post("/files", files={"file": ("a.txt", io.BytesIO(b"a"), "text/plain")})

    assert response.status_code == 401


def test_download_requires_authentication(client: TestClient):
    response = client.get("/files/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 401


def test_delete_requires_authentication(client: TestClient):
    response = client.delete("/files/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 401


# --- upload ------------------------------------------------------------------


def test_upload_returns_201_with_metadata(client: TestClient, user_headers: dict[str, str]):
    response = _upload(client, user_headers)

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "report.pdf"
    assert body["content_type"] == "application/pdf"
    assert body["size"] == len(b"hello world")
    assert "id" in body
    assert "storage_key" in body


def test_upload_stores_binary_via_storage_provider(
    client: TestClient, user_headers: dict[str, str], fake_storage: FakeStorageProvider
):
    response = _upload(client, user_headers, content=b"binary payload")

    body = response.json()
    stored = fake_storage.objects[(body["bucket"], body["storage_key"])]
    assert stored == b"binary payload"


# --- download ------------------------------------------------------------------


def test_download_returns_the_uploaded_bytes(client: TestClient, user_headers: dict[str, str]):
    upload_response = _upload(client, user_headers, content=b"hello world")
    file_id = upload_response.json()["id"]

    response = client.get(f"/files/{file_id}", headers=user_headers)

    assert response.status_code == 200
    assert response.content == b"hello world"
    assert response.headers["content-type"] == "application/pdf"


def test_download_missing_returns_404(client: TestClient, user_headers: dict[str, str]):
    response = client.get("/files/00000000-0000-0000-0000-000000000000", headers=user_headers)

    assert response.status_code == 404


# --- delete ------------------------------------------------------------------


def test_delete_removes_metadata_and_binary(
    client: TestClient, user_headers: dict[str, str], fake_storage: FakeStorageProvider
):
    upload_response = _upload(client, user_headers)
    body = upload_response.json()

    response = client.delete(f"/files/{body['id']}", headers=user_headers)

    assert response.status_code == 204
    assert (body["bucket"], body["storage_key"]) not in fake_storage.objects
    assert client.get(f"/files/{body['id']}", headers=user_headers).status_code == 404


def test_delete_missing_returns_404(client: TestClient, user_headers: dict[str, str]):
    response = client.delete("/files/00000000-0000-0000-0000-000000000000", headers=user_headers)

    assert response.status_code == 404
