import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.job_grade import JobGradeCreate, JobGradeResponse, JobGradeUpdate
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.job_grade import (
    DuplicateJobGradeCodeError,
    DuplicateJobGradeLevelError,
    JobGradeService,
)

router = APIRouter(prefix="/hr/job-grades", tags=["Job Grades"])


def get_job_grade_service() -> JobGradeService:
    return JobGradeService()


JobGradeServiceDep = Annotated[JobGradeService, Depends(get_job_grade_service)]

# HR Master/Reference Data Authorization Policy: Role Based (`RequireRole("admin")`)
# for create/update/delete; reads remain open to any authenticated user.
# Reopened per CTO decision H2 (`HOLIDAY_CALENDAR_DESIGN.md` addendum) -- see
# `api/holidays.py`'s identical comment for the full rationale.
RequireHrMasterDataAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


def get_job_grade_filters(
    level: Annotated[int | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`level`), scoped to Job Grades."""
    values: dict[str, Any] = {}
    if level is not None:
        values["level"] = level
    return FilterParams(values=values)


JobGradeFilters = Annotated[FilterParams, Depends(get_job_grade_filters)]


@router.post("", response_model=JobGradeResponse, status_code=status.HTTP_201_CREATED)
async def create_job_grade(
    data: JobGradeCreate, service: JobGradeServiceDep, _: RequireHrMasterDataAdmin
) -> JobGradeResponse:
    try:
        job_grade = await service.create(data)
    except DuplicateJobGradeCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job grade code already exists",
        ) from exc
    except DuplicateJobGradeLevelError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job grade level already exists",
        ) from exc
    return JobGradeResponse.model_validate(job_grade)


@router.get("", response_model=list[JobGradeResponse])
async def list_job_grades(service: JobGradeServiceDep, _: CurrentUser) -> list[JobGradeResponse]:
    job_grades = await service.list()
    return [JobGradeResponse.model_validate(job_grade) for job_grade in job_grades]


@router.get("/paginated", response_model=Page[JobGradeResponse])
async def list_job_grades_paginated(
    service: JobGradeServiceDep,
    pagination: Pagination,
    search: Search,
    filters: JobGradeFilters,
    _: CurrentUser,
) -> Page[JobGradeResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[JobGradeResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{job_grade_id}", response_model=JobGradeResponse)
async def get_job_grade(
    job_grade_id: uuid.UUID, service: JobGradeServiceDep, _: CurrentUser
) -> JobGradeResponse:
    job_grade = await service.get(job_grade_id)
    if job_grade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job grade not found")
    return JobGradeResponse.model_validate(job_grade)


@router.put("/{job_grade_id}", response_model=JobGradeResponse)
async def update_job_grade(
    job_grade_id: uuid.UUID,
    data: JobGradeUpdate,
    service: JobGradeServiceDep,
    _: RequireHrMasterDataAdmin,
) -> JobGradeResponse:
    try:
        job_grade = await service.update(job_grade_id, data)
    except DuplicateJobGradeCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job grade code already exists",
        ) from exc
    except DuplicateJobGradeLevelError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job grade level already exists",
        ) from exc
    if job_grade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job grade not found")
    return JobGradeResponse.model_validate(job_grade)


@router.delete("/{job_grade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_grade(
    job_grade_id: uuid.UUID, service: JobGradeServiceDep, _: RequireHrMasterDataAdmin
) -> None:
    deleted = await service.delete(job_grade_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job grade not found")
