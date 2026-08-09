import uuid
from collections.abc import Callable, Sequence
from datetime import date

from eop_api.models.performance_review import PerformanceReview
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.performance_review import PerformanceReviewRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.performance_review import PerformanceReviewCreate, PerformanceReviewUpdate
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the employee referenced by a PerformanceReview does not exist."""


class InvalidPerformanceReviewPeriodError(Exception):
    """Raised when `review_period_end` is before `review_period_start`.

    A narrow data-integrity check, not a review-cadence or workflow rule --
    mirrors `ShiftService`'s own `start_time != end_time` sanity check.
    """


class PerformanceReviewService:
    """Business logic for `PerformanceReview`. Owns the transaction boundary via a UoW.

    Deliberately minimal: a single existence check on `employee_id`, a
    basic period sanity check, no uniqueness constraint (multiple reviews
    per employee are permitted), no rating/scoring/workflow of any kind.

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

            review = await PerformanceReviewRepository(uow.session).create(**data.model_dump())
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

    async def delete(self, review_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = PerformanceReviewRepository(uow.session)
            deleted = await repo.delete(review_id)
            if deleted:
                await uow.commit()
            return deleted
