from pydantic import BaseModel


class PerformanceDashboardResponse(BaseModel):
    kpi_count: int
    target_count: int
    achievement_count: int
