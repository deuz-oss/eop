import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    project_id: uuid.UUID
    assignee_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    status: str = Field(default="todo", min_length=1, max_length=50)
    due_date: date | None = None


class TaskUpdate(BaseModel):
    project_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = Field(default=None, min_length=1, max_length=50)
    due_date: date | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    assignee_id: uuid.UUID | None
    title: str
    status: str
    due_date: date | None
    created_at: datetime
    updated_at: datetime
