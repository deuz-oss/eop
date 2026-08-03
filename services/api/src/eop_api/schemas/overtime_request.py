import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class OvertimeRequestCreate(BaseModel):
    employee_id: uuid.UUID
    overtime_date: date
    start_time: time
    end_time: time
    status: str = Field(default="pending", min_length=1, max_length=50)
    reason: str | None = Field(default=None, max_length=2000)


class OvertimeRequestUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    overtime_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)
    reason: str | None = Field(default=None, max_length=2000)


class OvertimeRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    overtime_date: date
    start_time: time
    end_time: time
    status: str
    reason: str | None
    created_at: datetime
    updated_at: datetime
