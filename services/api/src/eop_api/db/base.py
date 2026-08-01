from sqlalchemy.orm import DeclarativeBase

from eop_api.db.mixins import (
    AuditMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UUIDMixin,
    VersionMixin,
)


class Base(DeclarativeBase):
    pass


class BaseEntity(
    UUIDMixin,
    TimestampMixin,
    AuditMixin,
    SoftDeleteMixin,
    VersionMixin,
    Base,
):
    __abstract__ = True
