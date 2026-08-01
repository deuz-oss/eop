import asyncio
from collections.abc import AsyncIterator
from typing import BinaryIO

from minio import Minio
from minio.error import S3Error

from eop_api.storage.base import StorageProvider
from eop_api.storage.exceptions import StorageObjectNotFoundError

_CHUNK_SIZE = 64 * 1024
_NOT_FOUND_CODES = {"NoSuchKey", "NoSuchObject"}


class MinIOStorageProvider(StorageProvider):
    """`StorageProvider` backed by MinIO (S3-compatible object storage).

    The `minio` SDK is synchronous; every call is pushed onto a worker thread
    via `asyncio.to_thread` so it never blocks the event loop.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        secure: bool = False,
    ) -> None:
        self._client = Minio(
            endpoint, access_key=access_key, secret_key=secret_key, secure=secure
        )

    async def _ensure_bucket(self, bucket: str) -> None:
        exists = await asyncio.to_thread(self._client.bucket_exists, bucket)
        if not exists:
            await asyncio.to_thread(self._client.make_bucket, bucket)

    async def upload(
        self, *, bucket: str, key: str, data: BinaryIO, length: int, content_type: str
    ) -> None:
        await self._ensure_bucket(bucket)
        await asyncio.to_thread(
            self._client.put_object, bucket, key, data, length, content_type
        )

    async def download(self, *, bucket: str, key: str) -> AsyncIterator[bytes]:
        try:
            response = await asyncio.to_thread(self._client.get_object, bucket, key)
        except S3Error as exc:
            if exc.code in _NOT_FOUND_CODES:
                raise StorageObjectNotFoundError(key) from exc
            raise

        async def _stream() -> AsyncIterator[bytes]:
            iterator = response.stream(_CHUNK_SIZE)
            try:
                while True:
                    chunk = await asyncio.to_thread(next, iterator, None)
                    if chunk is None:
                        break
                    yield chunk
            finally:
                await asyncio.to_thread(response.close)
                await asyncio.to_thread(response.release_conn)

        return _stream()

    async def delete(self, *, bucket: str, key: str) -> None:
        await asyncio.to_thread(self._client.remove_object, bucket, key)

    async def exists(self, *, bucket: str, key: str) -> bool:
        try:
            await asyncio.to_thread(self._client.stat_object, bucket, key)
            return True
        except S3Error as exc:
            if exc.code in _NOT_FOUND_CODES:
                return False
            raise
