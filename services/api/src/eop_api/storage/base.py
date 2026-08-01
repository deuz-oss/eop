import abc
from collections.abc import AsyncIterator
from typing import BinaryIO


class StorageProvider(abc.ABC):
    """Reusable abstraction over binary object storage.

    Business modules must never talk to a concrete backend (e.g. MinIO)
    directly -- everything goes through this interface via `FileService`.
    """

    @abc.abstractmethod
    async def upload(
        self, *, bucket: str, key: str, data: BinaryIO, length: int, content_type: str
    ) -> None:
        """Store `data` (exactly `length` bytes) under `key` in `bucket`."""
        ...

    @abc.abstractmethod
    async def download(self, *, bucket: str, key: str) -> AsyncIterator[bytes]:
        """Return an async byte-chunk stream for the object at `key` in `bucket`.

        Raises `StorageObjectNotFoundError` if the key does not exist.
        """
        ...

    @abc.abstractmethod
    async def delete(self, *, bucket: str, key: str) -> None:
        """Remove the object at `key` from `bucket`. A no-op if it doesn't exist."""
        ...

    @abc.abstractmethod
    async def exists(self, *, bucket: str, key: str) -> bool:
        """Return whether an object at `key` exists in `bucket`."""
        ...
