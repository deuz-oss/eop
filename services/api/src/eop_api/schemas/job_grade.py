import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobGradeCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    level: int
    description: str | None = Field(default=None, max_length=1000)


class JobGradeUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    level: int | None = None
    description: str | None = Field(default=None, max_length=1000)


class JobGradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    level: int
    description: str | None
    created_at: datetime
    updated_at: datetime
