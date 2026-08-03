import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from eop_api.core.attendance import EventSource, EventType


class AttendanceEventCreate(BaseModel):
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    event_type: EventType
    event_time: datetime
    source: EventSource
    remarks: str | None = Field(default=None, max_length=2000)


class AttendanceEventUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    shift_id: uuid.UUID | None = None
    event_type: EventType | None = None
    event_time: datetime | None = None
    source: EventSource | None = None
    remarks: str | None = Field(default=None, max_length=2000)


class AttendanceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    event_type: EventType
    event_time: datetime
    source: EventSource
    remarks: str | None
    created_at: datetime
    updated_at: datetime
