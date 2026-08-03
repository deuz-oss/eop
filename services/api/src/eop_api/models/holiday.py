from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Holiday(BaseEntity):
    """Global HR master data defining a single named non-working date.

    Deliberately independent of Organization, Department, Team, Position, and
    Location -- it has no hierarchy, no parent, and is not scoped to any of
    them. `code` and `holiday_date` are both globally unique.
    """

    __tablename__ = "holidays"
    __table_args__ = (
        UniqueConstraint("code", name="uq_holidays_code"),
        UniqueConstraint("holiday_date", name="uq_holidays_holiday_date"),
        Index("ix_holidays_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
    holiday_date: Mapped[date] = mapped_column(Date)
