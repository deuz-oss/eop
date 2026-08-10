import uuid
from decimal import Decimal

from pydantic import BaseModel


class ReportingLineResponse(BaseModel):
    achievement_id: uuid.UUID
    target_id: uuid.UUID
    kpi_id: uuid.UUID
    kpi_code: str
    kpi_name: str
    employee_id: uuid.UUID
    employee_number: str
    employee_full_name: str
    period_year: int
    period_month: int
    goal_value: Decimal
    actual_value: Decimal
