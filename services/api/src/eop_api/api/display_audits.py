import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.schemas.display_audit import (
    DisplayAuditCreate,
    DisplayAuditResponse,
    DisplayAuditUpdate,
)
from eop_api.schemas.pagination import Page
from eop_api.services.display_audit import (
    DisplayAuditAuthorizationDeniedError,
    DisplayAuditService,
    VisitNotFoundError,
)

router = APIRouter(prefix="/display-audits", tags=["Visit"])


def get_display_audit_service() -> DisplayAuditService:
    return DisplayAuditService()


DisplayAuditServiceDep = Annotated[DisplayAuditService, Depends(get_display_audit_service)]


@router.post("", response_model=DisplayAuditResponse, status_code=status.HTTP_201_CREATED)
async def create_display_audit(
    data: DisplayAuditCreate,
    service: DisplayAuditServiceDep,
    request_context: CurrentRequestContext,
) -> DisplayAuditResponse:
    try:
        audit = await service.create(data, request_context)
    except VisitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found"
        ) from exc
    except DisplayAuditAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return DisplayAuditResponse.model_validate(audit)


@router.get("", response_model=list[DisplayAuditResponse])
async def list_display_audits(
    service: DisplayAuditServiceDep, request_context: CurrentRequestContext
) -> list[DisplayAuditResponse]:
    audits = await service.list(request_context)
    return [DisplayAuditResponse.model_validate(item) for item in audits]


@router.get("/paginated", response_model=Page[DisplayAuditResponse])
async def list_display_audits_paginated(
    service: DisplayAuditServiceDep,
    pagination: Pagination,
    request_context: CurrentRequestContext,
    visit_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[DisplayAuditResponse]:
    page = await service.list_paginated(request_context, pagination, visit_id=visit_id)
    return Page(
        items=[DisplayAuditResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{audit_id}", response_model=DisplayAuditResponse)
async def get_display_audit(
    audit_id: uuid.UUID,
    service: DisplayAuditServiceDep,
    request_context: CurrentRequestContext,
) -> DisplayAuditResponse:
    try:
        audit = await service.get(audit_id, request_context)
    except DisplayAuditAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Display audit not found")
    return DisplayAuditResponse.model_validate(audit)


@router.put("/{audit_id}", response_model=DisplayAuditResponse)
async def update_display_audit(
    audit_id: uuid.UUID,
    data: DisplayAuditUpdate,
    service: DisplayAuditServiceDep,
    request_context: CurrentRequestContext,
) -> DisplayAuditResponse:
    try:
        audit = await service.update(audit_id, data, request_context)
    except DisplayAuditAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Display audit not found")
    return DisplayAuditResponse.model_validate(audit)


@router.delete("/{audit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_display_audit(
    audit_id: uuid.UUID,
    service: DisplayAuditServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(audit_id, request_context)
    except DisplayAuditAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Display audit not found")
