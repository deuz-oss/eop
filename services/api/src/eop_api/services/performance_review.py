import uuid
from collections.abc import Callable, Sequence
from datetime import date

from eop_api.core.performance import VALID_PERFORMANCE_REVIEW_TRANSITIONS, PerformanceReviewStatus
from eop_api.models.performance_review import PerformanceReview
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.performance_review import PerformanceReviewRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.performance_review import PerformanceReviewCreate, PerformanceReviewUpdate
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

# Fields considered "substantive review data" for the finalized-immutability
# invariant (Performance Iteration 2 D1, Approved): every field on
# `PerformanceReviewUpdate` except `status`, which is not on that schema at
# all -- lifecycle changes only ever go through `finalize`.
_SUBSTANTIVE_UPDATE_FIELDS = frozenset(
    {"employee_id", "review_period_start", "review_period_end", "notes"}
)


class EmployeeNotFoundError(Exception):
    """Raised when the employee referenced by a PerformanceReview does not exist."""


class InvalidPerformanceReviewPeriodError(Exception):
    """Raised when `review_period_end` is before `review_period_start`.

    A narrow data-integrity check, not a review-cadence or workflow rule --
    mirrors `ShiftService`'s own `start_time != end_time` sanity check.
    """


class PerformanceReviewFinalizedError(Exception):
    """Raised when an ordinary `update()` call attempts to change substantive
    review data on a `PerformanceReview` that is already `FINALIZED`.

    Per `docs/architecture/capabilities/performance/
    iteration-2-business-decision-package.md` (Approved, D1): finalized
    reviews must not become mutable through ordinary update operations.
    `status` itself is never part of `PerformanceReviewUpdate` -- lifecycle
    changes only ever go through `finalize`, which has its own dedicated
    validation (`InvalidPerformanceReviewTransitionError`).
    """


class InvalidPerformanceReviewTransitionError(Exception):
    """Raised when `finalize()` is called on a `PerformanceReview` that is not
    currently `DRAFT` -- including a review that is already `FINALIZED`
    (re-finalizing is rejected, not a no-op, mirroring
    `InvalidApplicationTransitionError`'s exact precedent: `FINALIZED` maps
    to an empty transition set in `VALID_PERFORMANCE_REVIEW_TRANSITIONS`).
    """


class PerformanceReviewService:
    """Business logic for `PerformanceReview`. Owns the transaction boundary via a UoW.

    Deliberately minimal: a single existence check on `employee_id`, a
    basic period sanity check, no uniqueness constraint (multiple reviews
    per employee are permitted), no rating/scoring/workflow of any kind.

    Iteration 2 adds a single admin-only lifecycle transition (`finalize`,
    `draft -> finalized`) via `VALID_PERFORMANCE_REVIEW_TRANSITIONS`
    (`core/performance.py`), mirroring `ApplicationService.transition`'s
    structure. `status` is never accepted by `PerformanceReviewUpdate`, so
    it can only ever change through `finalize`. Once `FINALIZED`, `update()`
    rejects any attempt to change substantive review data.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    @staticmethod
    def _validate_period(period_start: date, period_end: date) -> None:
        if period_end < period_start:
            raise InvalidPerformanceReviewPeriodError(
                f"review_period_end {period_end} is before review_period_start {period_start}"
            )

    async def create(self, data: PerformanceReviewCreate) -> PerformanceReview:
        self._validate_period(data.review_period_start, data.review_period_end)

        async with self._uow_factory() as uow:
            if not await HrEmployeeRepository(uow.session).exists(data.employee_id):
                raise EmployeeNotFoundError(str(data.employee_id))

            review = await PerformanceReviewRepository(uow.session).create(
                **data.model_dump(), status=PerformanceReviewStatus.DRAFT
            )
            await uow.commit()
            uow.session.expunge(review)
            return review

    async def get(self, review_id: uuid.UUID) -> PerformanceReview | None:
        async with self._uow_factory() as uow:
            review = await PerformanceReviewRepository(uow.session).get(review_id)
            if review is not None:
                uow.session.expunge(review)
            return review

    async def list(self) -> Sequence[PerformanceReview]:
        async with self._uow_factory() as uow:
            reviews = await PerformanceReviewRepository(uow.session).list()
            uow.session.expunge_all()
            return reviews

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[PerformanceReview]:
        async with self._uow_factory() as uow:
            page = await PerformanceReviewRepository(uow.session).paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(
        self, review_id: uuid.UUID, data: PerformanceReviewUpdate
    ) -> PerformanceReview | None:
        async with self._uow_factory() as uow:
            repo = PerformanceReviewRepository(uow.session)
            review = await repo.get(review_id)
            if review is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if review.status == PerformanceReviewStatus.FINALIZED and (
                _SUBSTANTIVE_UPDATE_FIELDS & values.keys()
            ):
                raise PerformanceReviewFinalizedError(
                    f"PerformanceReview {review_id} is finalized and cannot be modified"
                )

            period_start = values.get("review_period_start", review.review_period_start)
            period_end = values.get("review_period_end", review.review_period_end)
            if "review_period_start" in values or "review_period_end" in values:
                self._validate_period(period_start, period_end)

            if "employee_id" in values and not await HrEmployeeRepository(uow.session).exists(
                values["employee_id"]
            ):
                raise EmployeeNotFoundError(str(values["employee_id"]))

            updated = await repo.update(review_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def finalize(self, review_id: uuid.UUID) -> PerformanceReview | None:
        """`draft -> finalized`. Returns `None` if `review_id` doesn't exist.

        Raises `InvalidPerformanceReviewTransitionError` if the review is not
        currently `DRAFT` -- including if it is already `FINALIZED`, per
        `VALID_PERFORMANCE_REVIEW_TRANSITIONS` (`core/performance.py`), which
        maps `FINALIZED` to an empty transition set.
        """
        async with self._uow_factory() as uow:
            repo = PerformanceReviewRepository(uow.session)
            review = await repo.get(review_id)
            if review is None:
                return None

            current_status = review.status
            if (
                PerformanceReviewStatus.FINALIZED
                not in VALID_PERFORMANCE_REVIEW_TRANSITIONS[current_status]
            ):
                raise InvalidPerformanceReviewTransitionError(
                    f"Cannot finalize PerformanceReview {review_id} from status {current_status}"
                )

            updated = await repo.update(review_id, status=PerformanceReviewStatus.FINALIZED)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, review_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = PerformanceReviewRepository(uow.session)
            deleted = await repo.delete(review_id)
            if deleted:
                await uow.commit()
            return deleted
