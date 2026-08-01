import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    organization_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    status: str = Field(default="active", min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None


class ProjectUpdate(BaseModel):
    organization_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    status: str | None = Field(default=None, min_length=1, max_length=50)
    start_date: date | None = None
    end_date: date | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    status: str
    start_date: date | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime
