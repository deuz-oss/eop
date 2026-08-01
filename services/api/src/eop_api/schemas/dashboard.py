from pydantic import BaseModel


class DashboardResponse(BaseModel):
    organizations: int
    projects: int
    employees: int
    assignments: int
    tasks: int
    tasks_by_status: dict[str, int]
