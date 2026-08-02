from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.department import Department
    from eop_api.models.employee import Employee
    from eop_api.models.position import Position
    from eop_api.models.project import Project
    from eop_api.models.team import Team


class Organization(BaseEntity):
    __tablename__ = "organizations"
    __table_args__ = (Index("ix_organizations_name", "name"),)

    name: Mapped[str] = mapped_column(String(255))

    projects: Mapped[list[Project]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    employees: Mapped[list[Employee]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    departments: Mapped[list[Department]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    positions: Mapped[list[Position]] = relationship(back_populates="organization")
    teams: Mapped[list[Team]] = relationship(back_populates="organization")
