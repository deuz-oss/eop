import uuid
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict, Field


class ShiftCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    start_time: time
    end_time: time
    break_duration_minutes: int = 0
    grace_period_minutes: int = 0


class ShiftUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    start_time: time | None = None
    end_time: time | None = None
    break_duration_minutes: int | None = None
    grace_period_minutes: int | None = None


class ShiftResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    start_time: time
    end_time: time
    break_duration_minutes: int
    grace_period_minutes: int
    created_at: datetime
    updated_at: datetime
