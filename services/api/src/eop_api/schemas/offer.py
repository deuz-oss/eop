import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class OfferCreate(BaseModel):
    application_id: uuid.UUID
    issued_date: date
    notes: str | None = Field(default=None, max_length=2000)


class OfferUpdate(BaseModel):
    application_id: uuid.UUID | None = None
    issued_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    application_id: uuid.UUID
    issued_date: date
    notes: str | None
    created_at: datetime
    updated_at: datetime
