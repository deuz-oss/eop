from typing import Annotated

from fastapi import APIRouter, Depends

from eop_api.dependencies.auth import CurrentUser
from eop_api.schemas.performance_dashboard import PerformanceDashboardResponse
from eop_api.services.performance_dashboard import PerformanceDashboardService

router = APIRouter(prefix="/performance/dashboard", tags=["Performance Management"])


def get_performance_dashboard_service() -> PerformanceDashboardService:
    return PerformanceDashboardService()


PerformanceDashboardServiceDep = Annotated[
    PerformanceDashboardService, Depends(get_performance_dashboard_service)
]

# Authorization: any authenticated user (`CurrentUser`), no `RequireRole("admin")`
# gate -- aggregate counts are not gated the same way as the underlying
# resources' own CRUD endpoints in this codebase, mirroring the existing
# `/dashboard` endpoint's own established precedent exactly
# (`docs/architecture/capabilities/dashboard/
# iteration-1-scope-and-implementation-plan.md` §5).


@router.get("", response_model=PerformanceDashboardResponse)
async def get_performance_dashboard(
    service: PerformanceDashboardServiceDep, _: CurrentUser
) -> PerformanceDashboardResponse:
    return await service.get_summary()
