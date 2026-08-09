import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InterviewCreate(BaseModel):
    application_id: uuid.UUID
    scheduled_at: datetime
    notes: str | None = Field(default=None, max_length=2000)


class InterviewUpdate(BaseModel):
    application_id: uuid.UUID | None = None
    scheduled_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=2000)


class InterviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    scheduled_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime
