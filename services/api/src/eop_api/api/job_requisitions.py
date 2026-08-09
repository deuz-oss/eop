import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.job_requisition import (
    JobRequisitionCreate,
    JobRequisitionResponse,
    JobRequisitionUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.job_requisition import (
    DepartmentNotFoundError,
    DuplicateJobRequisitionCodeError,
    JobRequisitionService,
    OrganizationNotFoundError,
    PositionNotFoundError,
)

router = APIRouter(prefix="/recruitment/job-requisitions", tags=["Recruitment"])


def get_job_requisition_service() -> JobRequisitionService:
    return JobRequisitionService()


JobRequisitionServiceDep = Annotated[JobRequisitionService, Depends(get_job_requisition_service)]


@router.post("", response_model=JobRequisitionResponse, status_code=status.HTTP_201_CREATED)
async def create_job_requisition(
    data: JobRequisitionCreate, service: JobRequisitionServiceDep, _: CurrentUser
) -> JobRequisitionResponse:
    try:
        job_requisition = await service.create(data)
    except DuplicateJobRequisitionCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Job requisition code already exists"
        ) from exc
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        ) from exc
    except PositionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Position not found"
        ) from exc
    return JobRequisitionResponse.model_validate(job_requisition)


@router.get("", response_model=list[JobRequisitionResponse])
async def list_job_requisitions(
    service: JobRequisitionServiceDep, _: CurrentUser
) -> list[JobRequisitionResponse]:
    job_requisitions = await service.list()
    return [JobRequisitionResponse.model_validate(item) for item in job_requisitions]


@router.get("/paginated", response_model=Page[JobRequisitionResponse])
async def list_job_requisitions_paginated(
    service: JobRequisitionServiceDep,
    pagination: Pagination,
    search: Search,
    _: CurrentUser,
) -> Page[JobRequisitionResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[JobRequisitionResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{job_requisition_id}", response_model=JobRequisitionResponse)
async def get_job_requisition(
    job_requisition_id: uuid.UUID, service: JobRequisitionServiceDep, _: CurrentUser
) -> JobRequisitionResponse:
    job_requisition = await service.get(job_requisition_id)
    if job_requisition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job requisition not found"
        )
    return JobRequisitionResponse.model_validate(job_requisition)


@router.put("/{job_requisition_id}", response_model=JobRequisitionResponse)
async def update_job_requisition(
    job_requisition_id: uuid.UUID,
    data: JobRequisitionUpdate,
    service: JobRequisitionServiceDep,
    _: CurrentUser,
) -> JobRequisitionResponse:
    try:
        job_requisition = await service.update(job_requisition_id, data)
    except DuplicateJobRequisitionCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Job requisition code already exists"
        ) from exc
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        ) from exc
    except PositionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Position not found"
        ) from exc
    if job_requisition is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job requisition not found"
        )
    return JobRequisitionResponse.model_validate(job_requisition)


@router.delete("/{job_requisition_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_requisition(
    job_requisition_id: uuid.UUID, service: JobRequisitionServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(job_requisition_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job requisition not found"
        )
