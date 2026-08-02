from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.location import Location


class LocationType(BaseEntity):
    """Master data describing the kind of place a `Location` represents."""

    __tablename__ = "location_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_location_types_code"),
        Index("ix_location_types_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    locations: Mapped[list[Location]] = relationship(back_populates="location_type")
