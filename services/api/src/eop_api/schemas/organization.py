import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    created_at: datetime
    updated_at: datetime
