from typing import Annotated

from fastapi import APIRouter, Depends

from eop_api.dependencies.auth import CurrentUser
from eop_api.schemas.dashboard import DashboardResponse
from eop_api.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def get_dashboard_service() -> DashboardService:
    return DashboardService()


DashboardServiceDep = Annotated[DashboardService, Depends(get_dashboard_service)]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(service: DashboardServiceDep, _: CurrentUser) -> DashboardResponse:
    return await service.get_stats()
