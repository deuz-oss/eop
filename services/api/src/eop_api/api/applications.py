import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.application import (
    ApplicationCreate,
    ApplicationResponse,
    ApplicationTransitionRequest,
    ApplicationUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.application import (
    ApplicationService,
    CandidateNotFoundError,
    DuplicateApplicationError,
    InvalidApplicationTransitionError,
    JobRequisitionNotFoundError,
)

router = APIRouter(prefix="/recruitment/applications", tags=["Recruitment"])


def get_application_service() -> ApplicationService:
    return ApplicationService()


ApplicationServiceDep = Annotated[ApplicationService, Depends(get_application_service)]

# Recruitment Authorization Policy: Role Based (`RequireRole("admin")`) --
# see `api/job_requisitions.py`'s identical rationale.
RequireRecruitmentAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    data: ApplicationCreate, service: ApplicationServiceDep, _: RequireRecruitmentAdmin
) -> ApplicationResponse:
    try:
        application = await service.create(data)
    except CandidateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found"
        ) from exc
    except JobRequisitionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job requisition not found"
        ) from exc
    except DuplicateApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application already exists for this candidate and job requisition",
        ) from exc
    return ApplicationResponse.model_validate(application)


@router.get("", response_model=list[ApplicationResponse])
async def list_applications(
    service: ApplicationServiceDep, _: RequireRecruitmentAdmin
) -> list[ApplicationResponse]:
    applications = await service.list()
    return [ApplicationResponse.model_validate(item) for item in applications]


@router.get("/paginated", response_model=Page[ApplicationResponse])
async def list_applications_paginated(
    service: ApplicationServiceDep,
    pagination: Pagination,
    search: Search,
    _: RequireRecruitmentAdmin,
) -> Page[ApplicationResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[ApplicationResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{application_id}", response_model=ApplicationResponse)
async def get_application(
    application_id: uuid.UUID, service: ApplicationServiceDep, _: RequireRecruitmentAdmin
) -> ApplicationResponse:
    application = await service.get(application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return ApplicationResponse.model_validate(application)


@router.put("/{application_id}", response_model=ApplicationResponse)
async def update_application(
    application_id: uuid.UUID,
    data: ApplicationUpdate,
    service: ApplicationServiceDep,
    _: RequireRecruitmentAdmin,
) -> ApplicationResponse:
    try:
        application = await service.update(application_id, data)
    except CandidateNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found"
        ) from exc
    except JobRequisitionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job requisition not found"
        ) from exc
    except DuplicateApplicationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Application already exists for this candidate and job requisition",
        ) from exc
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return ApplicationResponse.model_validate(application)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: uuid.UUID, service: ApplicationServiceDep, _: RequireRecruitmentAdmin
) -> None:
    deleted = await service.delete(application_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")


@router.post("/{application_id}/transition", response_model=ApplicationResponse)
async def transition_application(
    application_id: uuid.UUID,
    data: ApplicationTransitionRequest,
    service: ApplicationServiceDep,
    _: RequireRecruitmentAdmin,
) -> ApplicationResponse:
    """Moves `application_id` to `data.status`, per the approved lifecycle
    (`docs/architecture/capabilities/recruitment/
    iteration-2-business-decision-package.md`, D1). Mirrors `api/payroll_runs
    .py`'s `process_payroll_run` exception-mapping pattern: an invalid
    transition maps to 409, the project's standard conflict response.
    """
    try:
        application = await service.transition(application_id, data.status)
    except InvalidApplicationTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return ApplicationResponse.model_validate(application)
