from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class AuditLog(BaseEntity):
    """An immutable record of an action taken against some entity.

    Append-only: the repository/service layer never updates or deletes rows
    here, even though `BaseEntity` carries soft-delete/version columns shared
    by every entity in this project.
    """

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_type", "entity_type"),
        Index("ix_audit_logs_action", "action"),
        Index("ix_audit_logs_user_id", "user_id"),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID]
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
