import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class JobRequisitionCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=255)
    organization_id: uuid.UUID
    department_id: uuid.UUID
    position_id: uuid.UUID
    status: str = Field(min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=2000)


class JobRequisitionUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    organization_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = Field(default=None, max_length=2000)


class JobRequisitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    organization_id: uuid.UUID
    department_id: uuid.UUID
    position_id: uuid.UUID
    status: str
    description: str | None
    created_at: datetime
    updated_at: datetime
