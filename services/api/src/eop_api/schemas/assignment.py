import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class AssignmentCreate(BaseModel):
    employee_id: uuid.UUID
    project_id: uuid.UUID
    role: str = Field(min_length=1, max_length=100)
    start_date: date
    end_date: date | None = None


class AssignmentUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    role: str | None = Field(default=None, min_length=1, max_length=100)
    start_date: date | None = None
    end_date: date | None = None


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    project_id: uuid.UUID
    role: str
    start_date: date
    end_date: date | None
    created_at: datetime
    updated_at: datetime
