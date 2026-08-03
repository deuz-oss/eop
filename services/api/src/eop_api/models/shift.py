from __future__ import annotations

from datetime import time

from sqlalchemy import Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Shift(BaseEntity):
    """Global HR master data defining a reusable shift time template.

    Deliberately independent of Organization, Department, Team, Position, and
    Location -- it has no hierarchy, no parent, and is not scoped to any of
    them. `code` is globally unique. This is the shift *template* only:
    assigning a shift to an employee, a work calendar, and rostering are all
    out of scope and belong to future modules.
    """

    __tablename__ = "shifts"
    __table_args__ = (
        UniqueConstraint("code", name="uq_shifts_code"),
        Index("ix_shifts_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    break_duration_minutes: Mapped[int] = mapped_column(Integer, default=0)
    grace_period_minutes: Mapped[int] = mapped_column(Integer, default=0)
