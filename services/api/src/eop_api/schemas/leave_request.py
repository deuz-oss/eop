import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class LeaveRequestCreate(BaseModel):
    employee_id: uuid.UUID
    start_date: date
    end_date: date
    status: str = Field(default="pending", min_length=1, max_length=50)
    reason: str | None = Field(default=None, max_length=2000)


class LeaveRequestUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)
    reason: str | None = Field(default=None, max_length=2000)


class LeaveRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    start_date: date
    end_date: date
    status: str
    reason: str | None
    created_at: datetime
    updated_at: datetime
