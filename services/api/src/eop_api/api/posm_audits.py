import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.schemas.pagination import Page
from eop_api.schemas.posm_audit import PosmAuditCreate, PosmAuditResponse, PosmAuditUpdate
from eop_api.services.posm_audit import (
    PosmAuditAuthorizationDeniedError,
    PosmAuditService,
    VisitNotFoundError,
)

router = APIRouter(prefix="/posm-audits", tags=["Visit"])


def get_posm_audit_service() -> PosmAuditService:
    return PosmAuditService()


PosmAuditServiceDep = Annotated[PosmAuditService, Depends(get_posm_audit_service)]


@router.post("", response_model=PosmAuditResponse, status_code=status.HTTP_201_CREATED)
async def create_posm_audit(
    data: PosmAuditCreate,
    service: PosmAuditServiceDep,
    request_context: CurrentRequestContext,
) -> PosmAuditResponse:
    try:
        audit = await service.create(data, request_context)
    except VisitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found"
        ) from exc
    except PosmAuditAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return PosmAuditResponse.model_validate(audit)


@router.get("", response_model=list[PosmAuditResponse])
async def list_posm_audits(
    service: PosmAuditServiceDep, request_context: CurrentRequestContext
) -> list[PosmAuditResponse]:
    audits = await service.list(request_context)
    return [PosmAuditResponse.model_validate(item) for item in audits]


@router.get("/paginated", response_model=Page[PosmAuditResponse])
async def list_posm_audits_paginated(
    service: PosmAuditServiceDep,
    pagination: Pagination,
    request_context: CurrentRequestContext,
    visit_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[PosmAuditResponse]:
    page = await service.list_paginated(request_context, pagination, visit_id=visit_id)
    return Page(
        items=[PosmAuditResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{audit_id}", response_model=PosmAuditResponse)
async def get_posm_audit(
    audit_id: uuid.UUID,
    service: PosmAuditServiceDep,
    request_context: CurrentRequestContext,
) -> PosmAuditResponse:
    try:
        audit = await service.get(audit_id, request_context)
    except PosmAuditAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POSM audit not found")
    return PosmAuditResponse.model_validate(audit)


@router.put("/{audit_id}", response_model=PosmAuditResponse)
async def update_posm_audit(
    audit_id: uuid.UUID,
    data: PosmAuditUpdate,
    service: PosmAuditServiceDep,
    request_context: CurrentRequestContext,
) -> PosmAuditResponse:
    try:
        audit = await service.update(audit_id, data, request_context)
    except PosmAuditAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POSM audit not found")
    return PosmAuditResponse.model_validate(audit)


@router.delete("/{audit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_posm_audit(
    audit_id: uuid.UUID,
    service: PosmAuditServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(audit_id, request_context)
    except PosmAuditAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="POSM audit not found")
