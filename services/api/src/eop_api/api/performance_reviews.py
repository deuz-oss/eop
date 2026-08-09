import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.performance_review import (
    PerformanceReviewCreate,
    PerformanceReviewResponse,
    PerformanceReviewUpdate,
)
from eop_api.services.performance_review import (
    EmployeeNotFoundError,
    InvalidPerformanceReviewPeriodError,
    PerformanceReviewService,
)

router = APIRouter(prefix="/hr/performance-reviews", tags=["Performance"])


def get_performance_review_service() -> PerformanceReviewService:
    return PerformanceReviewService()


PerformanceReviewServiceDep = Annotated[
    PerformanceReviewService, Depends(get_performance_review_service)
]

# Performance Authorization Policy: Role Based (`RequireRole("admin")`) --
# reused unmodified, per explicit CPO/CTO instruction for Iteration 1;
# mirrors `api/job_requisitions.py`'s identical rationale (`PerformanceReview`
# carries an `employee_id` field, but Owner Only is not adopted here without
# a decision to do so -- admin-only for this iteration).
RequirePerformanceAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=PerformanceReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_performance_review(
    data: PerformanceReviewCreate,
    service: PerformanceReviewServiceDep,
    _: RequirePerformanceAdmin,
) -> PerformanceReviewResponse:
    try:
        review = await service.create(data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except InvalidPerformanceReviewPeriodError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return PerformanceReviewResponse.model_validate(review)


@router.get("", response_model=list[PerformanceReviewResponse])
async def list_performance_reviews(
    service: PerformanceReviewServiceDep, _: RequirePerformanceAdmin
) -> list[PerformanceReviewResponse]:
    reviews = await service.list()
    return [PerformanceReviewResponse.model_validate(item) for item in reviews]


@router.get("/paginated", response_model=Page[PerformanceReviewResponse])
async def list_performance_reviews_paginated(
    service: PerformanceReviewServiceDep,
    pagination: Pagination,
    search: Search,
    _: RequirePerformanceAdmin,
) -> Page[PerformanceReviewResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[PerformanceReviewResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{review_id}", response_model=PerformanceReviewResponse)
async def get_performance_review(
    review_id: uuid.UUID, service: PerformanceReviewServiceDep, _: RequirePerformanceAdmin
) -> PerformanceReviewResponse:
    review = await service.get(review_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Performance review not found"
        )
    return PerformanceReviewResponse.model_validate(review)


@router.put("/{review_id}", response_model=PerformanceReviewResponse)
async def update_performance_review(
    review_id: uuid.UUID,
    data: PerformanceReviewUpdate,
    service: PerformanceReviewServiceDep,
    _: RequirePerformanceAdmin,
) -> PerformanceReviewResponse:
    try:
        review = await service.update(review_id, data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except InvalidPerformanceReviewPeriodError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Performance review not found"
        )
    return PerformanceReviewResponse.model_validate(review)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_performance_review(
    review_id: uuid.UUID, service: PerformanceReviewServiceDep, _: RequirePerformanceAdmin
) -> None:
    deleted = await service.delete(review_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Performance review not found"
        )
