import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class MissionCreate(BaseModel):
    employee_id: uuid.UUID
    store_id: uuid.UUID
    scheduled_date: date


class MissionUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    store_id: uuid.UUID | None = None
    scheduled_date: date | None = None


class MissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    store_id: uuid.UUID
    scheduled_date: date
    created_at: datetime
    updated_at: datetime
