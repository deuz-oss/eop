from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.core.performance import PerformanceReviewStatus
from eop_api.db.base import BaseEntity


class PerformanceReview(BaseEntity):
    """A recorded performance review for an `HrEmployee`. Performance Iteration 1-2.

    Deliberately minimal -- no rating scale, no scoring formula, no
    manager/peer/self-review semantics. Not effective-dated: this is a
    discrete, one-time historical event (like `Interview`/`Offer`), not a
    "current state superseding prior state" concept the way
    `Compensation`/`WorkSchedule` are -- multiple rows per employee are
    independent historical events, not competing effective-dated versions
    of one thing (`iteration-1-scope-and-implementation-plan.md` §2).

    `review_period_start`/`review_period_end` are plain columns on this
    entity, mirroring `PayrollRun`'s own precedent -- no separate
    `PerformanceCycle`/`ReviewPeriod` entity is introduced. No uniqueness
    constraint -- multiple reviews per employee (including overlapping
    periods) are permitted; nothing establishes a review-cadence rule.

    `status` (`PerformanceReviewStatus`, `draft -> finalized`) is the
    Iteration 2 lifecycle boundary, decided in
    `docs/architecture/capabilities/performance/
    iteration-2-business-decision-package.md` (Approved, D1 -- Option B):
    admin-only, forward-only, `finalized` terminal, no reopening. Set only
    via `PerformanceReviewService.finalize` -- never a generic field on
    `PerformanceReviewUpdate`, mirroring `Application.status`'s exact
    precedent.
    """

    __tablename__ = "performance_reviews"
    __table_args__ = (Index("ix_performance_reviews_employee_id", "employee_id"),)

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    review_period_start: Mapped[date] = mapped_column(Date)
    review_period_end: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
    status: Mapped[PerformanceReviewStatus] = mapped_column(
        SqlEnum(
            PerformanceReviewStatus, name="performance_review_status", native_enum=False, length=20
        ),
        default=PerformanceReviewStatus.DRAFT,
    )
