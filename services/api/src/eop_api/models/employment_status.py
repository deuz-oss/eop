from __future__ import annotations

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class EmploymentStatus(BaseEntity):
    """Global HR master data describing an employee's current employment state.

    Deliberately independent of Organization, Department, Team, Position, and
    Location -- it has no hierarchy, no parent, and is not scoped to any of
    them. `code` is globally unique.
    """

    __tablename__ = "employment_statuses"
    __table_args__ = (
        UniqueConstraint("code", name="uq_employment_statuses_code"),
        Index("ix_employment_statuses_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
