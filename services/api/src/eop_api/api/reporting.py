import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.schemas.pagination import Page
from eop_api.schemas.reporting import ReportingLineResponse
from eop_api.schemas.search import FilterParams
from eop_api.services.reporting import ReportingService

router = APIRouter(prefix="/performance/reporting", tags=["Performance Management"])


def get_reporting_service() -> ReportingService:
    return ReportingService()


ReportingServiceDep = Annotated[ReportingService, Depends(get_reporting_service)]

# Authorization: Role Based (`RequireRole("admin")`) -- this endpoint exposes
# row-level, per-employee performance data (goal and actual values),
# organization-wide, not scoped to the caller -- the same exposure category
# as Kpi/Target/Achievement's own list/get endpoints, not Dashboard's
# aggregate-counts-only exposure (`docs/architecture/capabilities/
# performance/reporting-iteration-1-scope-and-implementation-plan.md` §5.5).
RequireReportingAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


def get_reporting_filters(
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    kpi_id: Annotated[uuid.UUID | None, Query()] = None,
    period_year: Annotated[int | None, Query()] = None,
    period_month: Annotated[int | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`employee_id`/`kpi_id`/`period_year`/
    `period_month`), scoped to Reporting -- the same dimensions
    `Target`/`Achievement` already expose one layer down."""
    values: dict[str, Any] = {}
    if employee_id is not None:
        values["employee_id"] = employee_id
    if kpi_id is not None:
        values["kpi_id"] = kpi_id
    if period_year is not None:
        values["period_year"] = period_year
    if period_month is not None:
        values["period_month"] = period_month
    return FilterParams(values=values)


ReportingFilters = Annotated[FilterParams, Depends(get_reporting_filters)]


@router.get("", response_model=Page[ReportingLineResponse])
async def list_reporting(
    service: ReportingServiceDep,
    pagination: Pagination,
    filters: ReportingFilters,
    _: RequireReportingAdmin,
) -> Page[ReportingLineResponse]:
    return await service.list_paginated(pagination, filters)
