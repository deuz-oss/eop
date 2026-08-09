from enum import StrEnum


class PerformanceReviewStatus(StrEnum):
    """Single source of truth for `PerformanceReview`'s lifecycle state.

    Per `docs/architecture/capabilities/performance/
    iteration-2-business-decision-package.md` (Approved, D1 -- Option B):
    `draft -> finalized` only, admin-only transition, no reopening, no
    backward transitions. Mirrors `ApplicationStatus`/`PayrollRunStatus`
    (`core/recruitment.py`/`core/payroll.py`): a fixed, closed enumeration
    owned by this capability alone, not the generic `pending`/`approved`/
    `rejected` string convention `ApprovalService` coordinates elsewhere.
    """

    DRAFT = "draft"
    FINALIZED = "finalized"


VALID_PERFORMANCE_REVIEW_TRANSITIONS: dict[
    PerformanceReviewStatus, frozenset[PerformanceReviewStatus]
] = {
    PerformanceReviewStatus.DRAFT: frozenset({PerformanceReviewStatus.FINALIZED}),
    PerformanceReviewStatus.FINALIZED: frozenset(),
}
"""Approved transition graph (D1, Option B). `FINALIZED` maps to the empty
set -- no transition out of `FINALIZED` is ever valid, including back to
`DRAFT` or re-finalizing, enforced by `PerformanceReviewService.finalize`.
"""
