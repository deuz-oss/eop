from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.employee import Employee
    from eop_api.models.project import Project


class Assignment(BaseEntity):
    __tablename__ = "assignments"
    __table_args__ = (
        UniqueConstraint("employee_id", "project_id", name="uq_assignments_employee_id_project_id"),
        Index("ix_assignments_project_id", "project_id"),
        Index("ix_assignments_employee_id", "employee_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"),
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"),
    )
    role: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)

    employee: Mapped[Employee] = relationship(back_populates="assignments")
    project: Mapped[Project] = relationship(back_populates="assignments")
