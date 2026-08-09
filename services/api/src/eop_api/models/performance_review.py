from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class PerformanceReview(BaseEntity):
    """A recorded performance review for an `HrEmployee`. Performance Iteration 1.

    Deliberately minimal, flat CRUD -- no status/lifecycle of its own, no
    rating scale, no scoring formula, no workflow. Not effective-dated:
    this is a discrete, one-time historical event (like `Interview`/
    `Offer`), not a "current state superseding prior state" concept the
    way `Compensation`/`WorkSchedule` are -- multiple rows per employee
    are independent historical events, not competing effective-dated
    versions of one thing (`iteration-1-scope-and-implementation-plan.md`
    §2).

    `review_period_start`/`review_period_end` are plain columns on this
    entity, mirroring `PayrollRun`'s own precedent -- no separate
    `PerformanceCycle`/`ReviewPeriod` entity is introduced. No uniqueness
    constraint -- multiple reviews per employee (including overlapping
    periods) are permitted; nothing establishes a review-cadence rule.
    """

    __tablename__ = "performance_reviews"
    __table_args__ = (Index("ix_performance_reviews_employee_id", "employee_id"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    review_period_start: Mapped[date] = mapped_column(Date)
    review_period_end: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
