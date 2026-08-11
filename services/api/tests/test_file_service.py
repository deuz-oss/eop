import io
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from typing import BinaryIO

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from eop_api import models  # noqa: F401 -- registers all models on Base.metadata
from eop_api.core.config import settings
from eop_api.db.base import Base
from eop_api.services.file import FileService
from eop_api.storage.base import StorageProvider
from eop_api.storage.exceptions import StorageObjectNotFoundError
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class FakeStorageProvider(StorageProvider):
    """In-memory `StorageProvider` test double -- no real MinIO involved."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.upload_calls: list[tuple[str, str]] = []
        self.delete_calls: list[tuple[str, str]] = []

    async def upload(
        self, *, bucket: str, key: str, data: BinaryIO, length: int, content_type: str
    ) -> None:
        self.upload_calls.append((bucket, key))
        self.objects[(bucket, key)] = data.read()

    async def download(self, *, bucket: str, key: str) -> AsyncIterator[bytes]:
        if (bucket, key) not in self.objects:
            raise StorageObjectNotFoundError(key)
        content = self.objects[(bucket, key)]

        async def _stream() -> AsyncIterator[bytes]:
            yield content

        return _stream()

    async def delete(self, *, bucket: str, key: str) -> None:
        self.delete_calls.append((bucket, key))
        self.objects.pop((bucket, key), None)

    async def exists(self, *, bucket: str, key: str) -> bool:
        return (bucket, key) in self.objects


@pytest.fixture
def storage() -> FakeStorageProvider:
    return FakeStorageProvider()


@pytest.fixture
async def service(storage: FakeStorageProvider) -> AsyncGenerator[FileService]:
    """A service backed by the real (migration-managed) `file_objects` table,
    but a fake, in-memory storage provider -- no real MinIO involved.

    Unlike the repository tests, the service commits internally (it owns the
    transaction boundary), so rows are truncated after each test instead of
    relying on a rolled-back transaction.
    """
    engine = create_async_engine(settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory: Callable[[], AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
    uow_factory: Callable[[], SQLAlchemyUnitOfWork] = lambda: SQLAlchemyUnitOfWork(session_factory)  # noqa: E731

    try:
        yield FileService(storage=storage, uow_factory=uow_factory, bucket="eop-files")
    finally:
        async with engine.begin() as conn:
            await conn.execute(text("TRUNCATE TABLE file_objects CASCADE"))
        await engine.dispose()


async def test_upload_persists_metadata_and_stores_binary(
    service: FileService, storage: FakeStorageProvider
):
    file_object = await service.upload(
        filename="report.pdf",
        content_type="application/pdf",
        size=11,
        data=io.BytesIO(b"hello world"),
    )

    assert file_object.id is not None
    assert file_object.filename == "report.pdf"
    assert file_object.content_type == "application/pdf"
    assert file_object.size == 11
    assert file_object.bucket == "eop-files"
    assert storage.objects[("eop-files", file_object.storage_key)] == b"hello world"


async def test_upload_is_visible_from_a_new_session(service: FileService):
    file_object = await service.upload(
        filename="a.txt", content_type="text/plain", size=1, data=io.BytesIO(b"a")
    )

    fetched = await service.get(file_object.id)

    assert fetched is not None
    assert fetched.id == file_object.id


async def test_get_missing_returns_none(service: FileService):
    assert await service.get(uuid.uuid4()) is None


async def test_download_returns_metadata_and_stream(service: FileService):
    file_object = await service.upload(
        filename="a.txt", content_type="text/plain", size=5, data=io.BytesIO(b"hello")
    )

    result = await service.download(file_object.id)

    assert result is not None
    fetched, stream = result
    assert fetched.id == file_object.id
    chunks = [chunk async for chunk in stream]
    assert b"".join(chunks) == b"hello"


async def test_download_missing_returns_none(service: FileService):
    assert await service.download(uuid.uuid4()) is None


async def test_delete_removes_metadata_and_binary(
    service: FileService, storage: FakeStorageProvider
):
    file_object = await service.upload(
        filename="a.txt", content_type="text/plain", size=1, data=io.BytesIO(b"a")
    )

    deleted = await service.delete(file_object.id)

    assert deleted is True
    assert await service.get(file_object.id) is None
    assert (("eop-files", file_object.storage_key)) not in storage.objects
    assert storage.delete_calls == [("eop-files", file_object.storage_key)]


async def test_delete_missing_returns_false(service: FileService, storage: FakeStorageProvider):
    assert await service.delete(uuid.uuid4()) is False
    assert storage.delete_calls == []
