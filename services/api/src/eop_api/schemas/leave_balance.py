import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeaveBalanceCreate(BaseModel):
    employee_id: uuid.UUID
    period_year: int
    allocated_days: int = 0
    used_days: int = 0
    remaining_days: int = 0


class LeaveBalanceUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    period_year: int | None = None
    allocated_days: int | None = None
    used_days: int | None = None
    remaining_days: int | None = None


class LeaveBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    period_year: int
    allocated_days: int
    used_days: int
    remaining_days: int
    created_at: datetime
    updated_at: datetime
