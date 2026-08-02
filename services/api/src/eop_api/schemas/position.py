import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PositionCreate(BaseModel):
    organization_id: uuid.UUID
    department_id: uuid.UUID
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class PositionUpdate(BaseModel):
    organization_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)


class PositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    department_id: uuid.UUID
    code: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
