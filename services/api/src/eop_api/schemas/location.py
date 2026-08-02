import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class LocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=50)
    location_type_id: uuid.UUID
    parent_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=1000)


class LocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    code: str | None = Field(default=None, min_length=1, max_length=50)
    location_type_id: uuid.UUID | None = None
    parent_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=1000)


class LocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str
    location_type_id: uuid.UUID
    parent_id: uuid.UUID | None
    description: str | None
    created_at: datetime
    updated_at: datetime
