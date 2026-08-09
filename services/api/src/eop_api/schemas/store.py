import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StoreCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    organization_id: uuid.UUID
    store_type_id: uuid.UUID
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    description: str | None = Field(default=None, max_length=1000)


class StoreUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    organization_id: uuid.UUID | None = None
    store_type_id: uuid.UUID | None = None
    address: str | None = Field(default=None, max_length=500)
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    description: str | None = Field(default=None, max_length=1000)


class StoreResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    organization_id: uuid.UUID
    store_type_id: uuid.UUID
    address: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    description: str | None
    created_at: datetime
    updated_at: datetime
