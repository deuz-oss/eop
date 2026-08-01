from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.models.file_object import FileObject
from eop_api.repositories.base import BaseRepository


class FileRepository(BaseRepository[FileObject]):
    """Data access layer for `FileObject`. Files are immutable: create, get, and delete only."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, FileObject)
