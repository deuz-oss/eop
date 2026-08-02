from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.department import Department
    from eop_api.models.organization import Organization


class Position(BaseEntity):
    """A job position belonging to exactly one Organization and Department.

    `code` is unique within an Organization, not globally. The database only
    enforces that `department_id` references a real department -- that the
    department belongs to the same `organization_id` is a cross-column
    invariant validated by `PositionService`, not expressible as a plain FK.

    Both FKs are `ON DELETE RESTRICT`: this is master data, so deleting an
    Organization or Department while Positions still reference it must fail
    at the database level rather than silently cascading the delete.
    """

    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_positions_organization_id_code"),
        Index("ix_positions_organization_id", "organization_id"),
        Index("ix_positions_department_id", "department_id"),
        Index("ix_positions_name", "name"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
    )
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    organization: Mapped[Organization] = relationship(back_populates="positions")
    department: Mapped[Department] = relationship(back_populates="positions")
