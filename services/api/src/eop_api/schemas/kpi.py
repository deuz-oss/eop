import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class KpiCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    unit: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class KpiUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    unit: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class KpiResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    unit: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime
