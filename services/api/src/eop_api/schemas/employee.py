import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    organization_id: uuid.UUID
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=100)


class EmployeeUpdate(BaseModel):
    organization_id: uuid.UUID | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=100)


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    title: str | None
    created_at: datetime
    updated_at: datetime
