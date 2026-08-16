from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.location_type import LocationType


class Location(BaseEntity):
    """An organizational place (site/facility), not a postal address.

    Locations form an adjacency-list tree via `parent_id`: unlimited depth,
    no cycle constraint at the schema/FK level -- `LocationService` rejects
    both self-parenting and multi-hop cycles at the service layer.
    `parent_id` is `ON DELETE RESTRICT` so deleting a
    parent that still has children fails at the database level -- callers
    must reassign or delete the children first.
    """

    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("code", name="uq_locations_code"),
        Index("ix_locations_name", "name"),
        Index("ix_locations_parent_id", "parent_id"),
        Index("ix_locations_location_type_id", "location_type_id"),
    )

    name: Mapped[str] = mapped_column(String(255))
    code: Mapped[str] = mapped_column(String(50))
    location_type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("location_types.id"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"), default=None
    )
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    location_type: Mapped[LocationType] = relationship(back_populates="locations")
    parent: Mapped[Location | None] = relationship(
        remote_side="Location.id", back_populates="children"
    )
    children: Mapped[list[Location]] = relationship(back_populates="parent", passive_deletes=True)
