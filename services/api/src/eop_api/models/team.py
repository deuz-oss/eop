from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.department import Department
    from eop_api.models.organization import Organization


class Team(BaseEntity):
    """A team belonging to exactly one Organization and Department.

    Teams form an adjacency-list tree via `parent_id`: unlimited depth, no
    cycle constraint at the schema/FK level -- `TeamService` rejects both
    self-parenting and multi-hop cycles at the service layer. Unlike
    `Department`, `parent_id` here is scoped two ways at once -- a parent
    Team must belong to the same Organization *and* the same Department --
    which is a cross-column invariant validated by `TeamService`, not
    expressible as a plain FK.

    All three FKs are `ON DELETE RESTRICT`: this is master data, so deleting
    an Organization, Department, or parent Team while Teams still reference
    it must fail at the database level rather than silently cascading the
    delete. `code` is unique within an Organization, not globally.
    """

    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_teams_organization_id_code"),
        Index("ix_teams_organization_id", "organization_id"),
        Index("ix_teams_department_id", "department_id"),
        Index("ix_teams_parent_id", "parent_id"),
        Index("ix_teams_name", "name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"), default=None
    )
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    organization: Mapped[Organization] = relationship(back_populates="teams")
    department: Mapped[Department] = relationship(back_populates="teams")
    parent: Mapped[Team | None] = relationship(remote_side="Team.id", back_populates="children")
    children: Mapped[list[Team]] = relationship(back_populates="parent", passive_deletes=True)
