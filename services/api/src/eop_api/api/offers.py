import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.offer import OfferCreate, OfferResponse, OfferUpdate
from eop_api.schemas.pagination import Page
from eop_api.services.offer import ApplicationNotFoundError, OfferService

router = APIRouter(prefix="/recruitment/offers", tags=["Recruitment"])


def get_offer_service() -> OfferService:
    return OfferService()


OfferServiceDep = Annotated[OfferService, Depends(get_offer_service)]

# Recruitment Authorization Policy: Role Based (`RequireRole("admin")`) --
# reused unmodified from `api/job_requisitions.py`'s identical rationale;
# no dedicated evaluator, no new authorization mechanism introduced.
RequireRecruitmentAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=OfferResponse, status_code=status.HTTP_201_CREATED)
async def create_offer(
    data: OfferCreate, service: OfferServiceDep, _: RequireRecruitmentAdmin
) -> OfferResponse:
    try:
        offer = await service.create(data)
    except ApplicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        ) from exc
    return OfferResponse.model_validate(offer)


@router.get("", response_model=list[OfferResponse])
async def list_offers(service: OfferServiceDep, _: RequireRecruitmentAdmin) -> list[OfferResponse]:
    offers = await service.list()
    return [OfferResponse.model_validate(item) for item in offers]


@router.get("/paginated", response_model=Page[OfferResponse])
async def list_offers_paginated(
    service: OfferServiceDep,
    pagination: Pagination,
    search: Search,
    _: RequireRecruitmentAdmin,
) -> Page[OfferResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[OfferResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{offer_id}", response_model=OfferResponse)
async def get_offer(
    offer_id: uuid.UUID, service: OfferServiceDep, _: RequireRecruitmentAdmin
) -> OfferResponse:
    offer = await service.get(offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return OfferResponse.model_validate(offer)


@router.put("/{offer_id}", response_model=OfferResponse)
async def update_offer(
    offer_id: uuid.UUID,
    data: OfferUpdate,
    service: OfferServiceDep,
    _: RequireRecruitmentAdmin,
) -> OfferResponse:
    try:
        offer = await service.update(offer_id, data)
    except ApplicationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Application not found"
        ) from exc
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
    return OfferResponse.model_validate(offer)


@router.delete("/{offer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_offer(
    offer_id: uuid.UUID, service: OfferServiceDep, _: RequireRecruitmentAdmin
) -> None:
    deleted = await service.delete(offer_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Offer not found")
