from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.store_type import StoreType


class Store(BaseEntity):
    """A retail outlet / point of sale field operations visits.

    The single aggregate fulfilling the roadmap's "Customer", "Store",
    "Outlet", "Modern Trade"/"General Trade"/"Store Classification", and
    "Geolocation" items (`docs/architecture/capabilities/store/
    iteration-1-scope-and-implementation-plan.md` §1/§2) -- Customer and
    Store are the same real-world entity in this product's domain language,
    not two separate aggregates; "Outlet" is a synonym, not a distinct
    concept.

    `store_type_id` covers Modern Trade/General Trade/Store Classification
    collectively (§4) -- a free-form lookup, not three separate fields.
    `latitude`/`longitude` are the minimum Geolocation representation (§5):
    plain nullable coordinate columns, no GIS/mapping infrastructure.

    Deliberately flat CRUD -- no status/lifecycle, no relationship to
    `HrEmployee`, `Location`, or any Territory/Region/Area concept (§6/§9).
    """

    __tablename__ = "stores"
    __table_args__ = (
        UniqueConstraint("code", name="uq_stores_code"),
        Index("ix_stores_name", "name"),
        Index("ix_stores_organization_id", "organization_id"),
        Index("ix_stores_store_type_id", "store_type_id"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
    )
    store_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("store_types.id", ondelete="RESTRICT"),
    )
    address: Mapped[str | None] = mapped_column(String(500), default=None)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), default=None)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), default=None)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    store_type: Mapped[StoreType] = relationship(back_populates="stores")
