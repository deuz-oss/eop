import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.kpi import KpiCreate, KpiResponse, KpiUpdate
from eop_api.schemas.pagination import Page
from eop_api.services.kpi import DuplicateKpiCodeError, KpiService

router = APIRouter(prefix="/kpis", tags=["Performance Management"])


def get_kpi_service() -> KpiService:
    return KpiService()


KpiServiceDep = Annotated[KpiService, Depends(get_kpi_service)]

# KPI Authorization Policy: Role Based (`RequireRole("admin")`) -- `Kpi` is
# definition-only, admin-managed reference data with no natural
# owner-employee field, the same structural reason `StoreType`/`JobGrade`
# use this mechanism. Reuses the same "admin" role/mechanism, no new
# authorization framework introduced.
RequireKpiAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=KpiResponse, status_code=status.HTTP_201_CREATED)
async def create_kpi(data: KpiCreate, service: KpiServiceDep, _: RequireKpiAdmin) -> KpiResponse:
    try:
        kpi = await service.create(data)
    except DuplicateKpiCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="KPI code already exists"
        ) from exc
    return KpiResponse.model_validate(kpi)


@router.get("", response_model=list[KpiResponse])
async def list_kpis(service: KpiServiceDep, _: RequireKpiAdmin) -> list[KpiResponse]:
    kpis = await service.list()
    return [KpiResponse.model_validate(item) for item in kpis]


@router.get("/paginated", response_model=Page[KpiResponse])
async def list_kpis_paginated(
    service: KpiServiceDep, pagination: Pagination, search: Search, _: RequireKpiAdmin
) -> Page[KpiResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[KpiResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{kpi_id}", response_model=KpiResponse)
async def get_kpi(kpi_id: uuid.UUID, service: KpiServiceDep, _: RequireKpiAdmin) -> KpiResponse:
    kpi = await service.get(kpi_id)
    if kpi is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found")
    return KpiResponse.model_validate(kpi)


@router.put("/{kpi_id}", response_model=KpiResponse)
async def update_kpi(
    kpi_id: uuid.UUID, data: KpiUpdate, service: KpiServiceDep, _: RequireKpiAdmin
) -> KpiResponse:
    try:
        kpi = await service.update(kpi_id, data)
    except DuplicateKpiCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="KPI code already exists"
        ) from exc
    if kpi is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found")
    return KpiResponse.model_validate(kpi)


@router.delete("/{kpi_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kpi(kpi_id: uuid.UUID, service: KpiServiceDep, _: RequireKpiAdmin) -> None:
    deleted = await service.delete(kpi_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found")
