from __future__ import annotations

from sqlalchemy import Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class JobGrade(BaseEntity):
    """Global HR master data ranking positions by seniority/pay grade.

    Deliberately independent of Organization, Department, Team, and
    Position -- it has no hierarchy, no parent, and is not scoped to any of
    them. `code` and `level` are both globally unique.
    """

    __tablename__ = "job_grades"
    __table_args__ = (
        UniqueConstraint("code", name="uq_job_grades_code"),
        UniqueConstraint("level", name="uq_job_grades_level"),
        Index("ix_job_grades_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    level: Mapped[int] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
