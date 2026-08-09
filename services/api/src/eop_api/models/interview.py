from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Interview(BaseEntity):
    """A recorded interview for an `Application`. Recruitment Iteration 3.

    Deliberately minimal, flat CRUD -- no status/lifecycle of its own.
    `Application` owns the recruitment lifecycle (Iteration 2,
    `iteration-2-business-decision-package.md`); `Interview` supports it
    without duplicating or competing with it. No coupling to
    `ApplicationService.transition` exists or is added here -- whether
    entering `interviewing` should require an `Interview` row is an
    unresolved business question, not assumed either way
    (`iteration-3-scope-and-implementation-plan.md` §2).

    No `type`/`interviewer`/`location` field -- none is justified by an
    accepted business requirement (`iteration-3-scope-and-implementation-
    plan.md` §2); a future iteration may add them once decided. Multiple
    `Interview` rows per `Application` are permitted (no uniqueness
    constraint) -- nothing establishes a single-interview-only rule.
    """

    __tablename__ = "interviews"
    __table_args__ = (Index("ix_interviews_application_id", "application_id"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"),
    )
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
