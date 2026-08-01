from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.assignment import Assignment
    from eop_api.models.organization import Organization
    from eop_api.models.task import Task


class Employee(BaseEntity):
    __tablename__ = "employees"
    __table_args__ = (
        UniqueConstraint("email", name="uq_employees_email"),
        Index("ix_employees_organization_id", "organization_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(100), default=None)

    organization: Mapped[Organization] = relationship(back_populates="employees")
    assignments: Mapped[list[Assignment]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    assigned_tasks: Mapped[list[Task]] = relationship(back_populates="assignee")
