import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.organization import (
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.organization import OrganizationService

router = APIRouter(prefix="/organizations", tags=["Organizations"])


def get_organization_service() -> OrganizationService:
    return OrganizationService()


OrganizationServiceDep = Annotated[OrganizationService, Depends(get_organization_service)]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    data: OrganizationCreate, service: OrganizationServiceDep
) -> OrganizationResponse:
    organization = await service.create(data)
    return OrganizationResponse.model_validate(organization)


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(service: OrganizationServiceDep) -> list[OrganizationResponse]:
    organizations = await service.list()
    return [OrganizationResponse.model_validate(organization) for organization in organizations]


@router.get("/paginated", response_model=Page[OrganizationResponse])
async def list_organizations_paginated(
    service: OrganizationServiceDep, pagination: Pagination, search: Search
) -> Page[OrganizationResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[OrganizationResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: uuid.UUID, service: OrganizationServiceDep
) -> OrganizationResponse:
    organization = await service.get(organization_id)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationResponse.model_validate(organization)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: uuid.UUID, data: OrganizationUpdate, service: OrganizationServiceDep
) -> OrganizationResponse:
    organization = await service.update(organization_id, data)
    if organization is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    return OrganizationResponse.model_validate(organization)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_organization(organization_id: uuid.UUID, service: OrganizationServiceDep) -> None:
    deleted = await service.delete(organization_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
