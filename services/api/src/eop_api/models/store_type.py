from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.store import Store


class StoreType(BaseEntity):
    """Master data describing a `Store`'s trade-channel classification
    (e.g. Modern Trade, General Trade).

    Free-form, admin-manageable lookup, mirroring `LocationType` exactly --
    not a fixed enum, since trade-channel taxonomies vary per organization
    and no closed value set is named anywhere in product scope
    (`docs/architecture/capabilities/store/
    iteration-1-scope-and-implementation-plan.md` §4).
    """

    __tablename__ = "store_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_store_types_code"),
        Index("ix_store_types_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)

    stores: Mapped[list[Store]] = relationship(back_populates="store_type")
