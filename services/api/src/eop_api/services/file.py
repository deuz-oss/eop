import uuid
from collections.abc import AsyncIterator, Callable
from typing import BinaryIO

from eop_api.core.config import settings
from eop_api.models.file_object import FileObject
from eop_api.repositories.file import FileRepository
from eop_api.storage.base import StorageProvider
from eop_api.storage.minio_provider import MinIOStorageProvider
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


def _default_storage_provider() -> StorageProvider:
    return MinIOStorageProvider(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


class FileService:
    """Business logic for `FileObject`. Owns the transaction boundary via a UoW.

    Persists metadata in Postgres and delegates binary storage to a
    `StorageProvider`; nothing else talks to the provider directly.
    """

    def __init__(
        self,
        storage: StorageProvider | None = None,
        uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork,
        bucket: str | None = None,
    ) -> None:
        self._storage = storage or _default_storage_provider()
        self._uow_factory = uow_factory
        self._bucket = bucket or settings.minio_bucket

    async def upload(
        self, *, filename: str, content_type: str, size: int, data: BinaryIO
    ) -> FileObject:
        """Store the binary content first, then persist metadata.

        This ordering means a storage failure never leaves behind a metadata
        row with no corresponding object; at worst, a metadata failure after
        a successful upload leaves an unreferenced (harmless) blob in storage.
        """
        storage_key = str(uuid.uuid4())
        await self._storage.upload(
            bucket=self._bucket,
            key=storage_key,
            data=data,
            length=size,
            content_type=content_type,
        )

        async with self._uow_factory() as uow:
            repo = FileRepository(uow.session)
            file_object = await repo.create(
                filename=filename,
                content_type=content_type,
                size=size,
                storage_key=storage_key,
                bucket=self._bucket,
            )
            await uow.commit()
            uow.session.expunge(file_object)
            return file_object

    async def get(self, file_id: uuid.UUID) -> FileObject | None:
        async with self._uow_factory() as uow:
            repo = FileRepository(uow.session)
            file_object = await repo.get(file_id)
            if file_object is not None:
                uow.session.expunge(file_object)
            return file_object

    async def download(self, file_id: uuid.UUID) -> tuple[FileObject, AsyncIterator[bytes]] | None:
        file_object = await self.get(file_id)
        if file_object is None:
            return None
        stream = await self._storage.download(
            bucket=file_object.bucket, key=file_object.storage_key
        )
        return file_object, stream

    async def delete(self, file_id: uuid.UUID) -> bool:
        """Delete the storage object first, then the metadata row.

        This ordering keeps the operation safely retryable: `StorageProvider.delete`
        is a no-op if the key is already gone, so retrying after a failed commit
        just re-runs an already-satisfied delete before removing the row.
        """
        async with self._uow_factory() as uow:
            repo = FileRepository(uow.session)
            file_object = await repo.get(file_id)
            if file_object is None:
                return False

            await self._storage.delete(bucket=file_object.bucket, key=file_object.storage_key)
            await repo.delete(file_id)
            await uow.commit()
            return True
