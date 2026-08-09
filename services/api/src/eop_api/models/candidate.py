from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Candidate(BaseEntity):
    """A person applying to a `JobRequisition`. Explicitly not an `HrEmployee`
    -- candidates are not employees, and this entity shares no foreign key
    relationship with `HrEmployee`, mirroring `HrEmployee`'s own documented
    independence from Project Tracking's `Employee`
    (`iteration-1-scope-and-implementation-plan.md` §1).

    Recruitment master data for a person: `first_name`/`last_name`/
    `full_name`/`email`/`phone`, the same field set `HrEmployee` itself
    uses for the equivalent person-identity fields.
    """

    __tablename__ = "candidates"
    __table_args__ = (UniqueConstraint("email", name="uq_candidates_email"),)

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50), default=None)
