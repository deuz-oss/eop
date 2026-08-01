from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class FileObject(BaseEntity):
    """Metadata record for a binary file stored via `StorageProvider`.

    Infrastructure only: no ownership, no entity references. Files are
    immutable -- rows are never updated after creation -- but this still
    inherits `BaseEntity` like every other entity in the project, even
    though some of its columns (e.g. soft-delete, version) go unused here.
    """

    __tablename__ = "file_objects"

    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(255))
    size: Mapped[int] = mapped_column(BigInteger)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    bucket: Mapped[str] = mapped_column(String(255))
