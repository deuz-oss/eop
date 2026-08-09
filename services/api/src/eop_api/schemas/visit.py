import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VisitCreate(BaseModel):
    employee_id: uuid.UUID
    store_id: uuid.UUID
    visited_at: datetime
    notes: str | None = Field(default=None, max_length=2000)


class VisitUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    store_id: uuid.UUID | None = None
    visited_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    store_id: uuid.UUID
    visited_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime
