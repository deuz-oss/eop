import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DeductionTypeCreate(BaseModel):
    code: str
    name: str
    description: str | None = None


class DeductionTypeUpdate(BaseModel):
    code: str | None = None
    name: str | None = None
    description: str | None = None


class DeductionTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
