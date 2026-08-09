import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.interview import InterviewCreate, InterviewResponse, InterviewUpdate
from eop_api.schemas.pagination import Page
from eop_api.services.interview import ApplicationNotFoundError, InterviewService

router = APIRouter(prefix="/recruitment/interviews", tags=["Recruitment"])


def get_interview_service() -> InterviewService:
    return InterviewService()


InterviewServiceDep = Annotated[InterviewService, Depends(get_interview_service)]

# Recruitment Authorization Policy: Role Based (`RequireRole("admin")`) --
# reused unmodified from `api/job_requisitions.py`'s identical rationale;
# no dedicated evaluator, no new authorization mechanism introduced.
RequireRecruitmentAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=InterviewResponse, status_code=status.HTTP_201_CREATED)
async def create_interview(
    data: InterviewCreate, service: InterviewServiceDep, _: RequireRecruitmentAdmin
) -> InterviewResponse:
    try:
        interview = await service.create(data)
    except ApplicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        ) from exc
    return InterviewResponse.model_validate(interview)


@router.get("", response_model=list[InterviewResponse])
async def list_interviews(
    service: InterviewServiceDep, _: RequireRecruitmentAdmin
) -> list[InterviewResponse]:
    interviews = await service.list()
    return [InterviewResponse.model_validate(item) for item in interviews]


@router.get("/paginated", response_model=Page[InterviewResponse])
async def list_interviews_paginated(
    service: InterviewServiceDep,
    pagination: Pagination,
    search: Search,
    _: RequireRecruitmentAdmin,
) -> Page[InterviewResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[InterviewResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{interview_id}", response_model=InterviewResponse)
async def get_interview(
    interview_id: uuid.UUID, service: InterviewServiceDep, _: RequireRecruitmentAdmin
) -> InterviewResponse:
    interview = await service.get(interview_id)
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return InterviewResponse.model_validate(interview)


@router.put("/{interview_id}", response_model=InterviewResponse)
async def update_interview(
    interview_id: uuid.UUID,
    data: InterviewUpdate,
    service: InterviewServiceDep,
    _: RequireRecruitmentAdmin,
) -> InterviewResponse:
    try:
        interview = await service.update(interview_id, data)
    except ApplicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        ) from exc
    if interview is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
    return InterviewResponse.model_validate(interview)


@router.delete("/{interview_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_interview(
    interview_id: uuid.UUID, service: InterviewServiceDep, _: RequireRecruitmentAdmin
) -> None:
    deleted = await service.delete(interview_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview not found")
