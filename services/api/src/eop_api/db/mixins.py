import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class AuditMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(default=None)


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    is_deleted: Mapped[bool] = mapped_column(default=False)


class VersionMixin:
    version: Mapped[int] = mapped_column(default=1)


class EffectiveDatingMixin:
    """Column-only contribution of an effective-dated validity period.

    `docs/architecture/capabilities/effective-dating/decision.md` §12:
    Effective Dating owns no persistence of its own -- this mixin
    contributes exactly two columns to the consuming entity's own table,
    the same way `VersionMixin` contributes `version`. No behavior,
    validation, or query method belongs here; interpreting these columns
    (e.g. resolving what is effective as of a date) is
    `EffectiveDatingEvaluator`'s responsibility, not this mixin's.

    `effective_to = None` means open-ended -- still effective, with no
    known end date.
    """

    effective_from: Mapped[date] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date, default=None)
