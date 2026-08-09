from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Offer(BaseEntity):
    """A recorded offer for an `Application`. Recruitment Iteration 3.

    Deliberately minimal, flat CRUD -- no status/lifecycle of its own, no
    acceptance/rejection/expiry tracking, and deliberately no monetary/
    compensation field: whether an offer needs terms, and what shape they
    take, is an unresolved business question this entity does not answer
    (`iteration-3-scope-and-implementation-plan.md` §2) -- it is never
    silently derived from Payroll `Compensation`. `Application` owns the
    recruitment lifecycle (Iteration 2); `Offer` supports it without
    duplicating or competing with it. No coupling to `ApplicationService
    .transition` exists or is added here.

    Multiple `Offer` rows per `Application` are permitted (no uniqueness
    constraint) -- nothing establishes a single-offer-only rule.
    """

    __tablename__ = "offers"
    __table_args__ = (Index("ix_offers_application_id", "application_id"),)

    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="RESTRICT"),
    )
    issued_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
