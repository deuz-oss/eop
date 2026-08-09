import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ApplicationCreate(BaseModel):
    candidate_id: uuid.UUID
    job_requisition_id: uuid.UUID
    status: str = Field(min_length=1, max_length=50)
    applied_date: date


class ApplicationUpdate(BaseModel):
    candidate_id: uuid.UUID | None = None
    job_requisition_id: uuid.UUID | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)
    applied_date: date | None = None


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    job_requisition_id: uuid.UUID
    status: str
    applied_date: date
    created_at: datetime
    updated_at: datetime
