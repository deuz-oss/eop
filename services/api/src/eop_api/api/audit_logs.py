from typing import Annotated

from fastapi import APIRouter, Depends

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.audit_log import AuditLogResponse
from eop_api.schemas.pagination import Page
from eop_api.services.audit_log import AuditLogService

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


def get_audit_log_service() -> AuditLogService:
    return AuditLogService()


AuditLogServiceDep = Annotated[AuditLogService, Depends(get_audit_log_service)]


@router.get("", response_model=Page[AuditLogResponse])
async def list_audit_logs(
    service: AuditLogServiceDep, pagination: Pagination, search: Search, _: CurrentUser
) -> Page[AuditLogResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[AuditLogResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )
