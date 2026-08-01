from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity
from eop_api.models.user_role import user_roles

if TYPE_CHECKING:
    from eop_api.models.user import User


class Role(BaseEntity):
    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("name", name="uq_roles_name"),)

    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), default=None)

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")
