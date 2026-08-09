import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.candidate import CandidateCreate, CandidateResponse, CandidateUpdate
from eop_api.schemas.pagination import Page
from eop_api.services.candidate import CandidateService, DuplicateCandidateEmailError

router = APIRouter(prefix="/recruitment/candidates", tags=["Recruitment"])


def get_candidate_service() -> CandidateService:
    return CandidateService()


CandidateServiceDep = Annotated[CandidateService, Depends(get_candidate_service)]


@router.post("", response_model=CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    data: CandidateCreate, service: CandidateServiceDep, _: CurrentUser
) -> CandidateResponse:
    try:
        candidate = await service.create(data)
    except DuplicateCandidateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Candidate email already exists"
        ) from exc
    return CandidateResponse.model_validate(candidate)


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(service: CandidateServiceDep, _: CurrentUser) -> list[CandidateResponse]:
    candidates = await service.list()
    return [CandidateResponse.model_validate(item) for item in candidates]


@router.get("/paginated", response_model=Page[CandidateResponse])
async def list_candidates_paginated(
    service: CandidateServiceDep,
    pagination: Pagination,
    search: Search,
    _: CurrentUser,
) -> Page[CandidateResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[CandidateResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(
    candidate_id: uuid.UUID, service: CandidateServiceDep, _: CurrentUser
) -> CandidateResponse:
    candidate = await service.get(candidate_id)
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return CandidateResponse.model_validate(candidate)


@router.put("/{candidate_id}", response_model=CandidateResponse)
async def update_candidate(
    candidate_id: uuid.UUID,
    data: CandidateUpdate,
    service: CandidateServiceDep,
    _: CurrentUser,
) -> CandidateResponse:
    try:
        candidate = await service.update(candidate_id, data)
    except DuplicateCandidateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Candidate email already exists"
        ) from exc
    if candidate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return CandidateResponse.model_validate(candidate)


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: uuid.UUID, service: CandidateServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(candidate_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
