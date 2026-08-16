from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.organization import Organization
    from eop_api.models.position import Position
    from eop_api.models.team import Team


class Department(BaseEntity):
    """An organizational unit belonging to exactly one Organization.

    Departments form an adjacency-list tree via `parent_id`: unlimited depth,
    no cycle constraint at the schema/FK level -- `DepartmentService` rejects
    both self-parenting and multi-hop cycles at the service layer.
    `parent_id` is `ON DELETE RESTRICT` so deleting a
    parent that still has children fails at the database level -- callers
    must reassign or delete the children first. `code` is unique within an
    Organization, not globally.
    """

    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_departments_organization_id_code"),
        Index("ix_departments_organization_id", "organization_id"),
        Index("ix_departments_name", "name"),
        Index("ix_departments_parent_id", "parent_id"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
    )
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"), default=None
    )
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    organization: Mapped[Organization] = relationship(back_populates="departments")
    parent: Mapped[Department | None] = relationship(
        remote_side="Department.id", back_populates="children"
    )
    children: Mapped[list[Department]] = relationship(back_populates="parent", passive_deletes=True)
    positions: Mapped[list[Position]] = relationship(back_populates="department")
    teams: Mapped[list[Team]] = relationship(back_populates="department")
