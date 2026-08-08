import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PayrollStatutoryParameterCreate(BaseModel):
    key: str
    value: Decimal
    effective_from: date
    effective_to: date | None = None
    description: str | None = None


class PayrollStatutoryParameterUpdate(BaseModel):
    """Only `description` is updatable -- `key`/`value`/effective period
    changes to an existing row would mutate a historical configuration fact
    in place, the same reason `CompensationUpdate` restricts itself to
    `is_active`. Recording a new rate uses `PayrollStatutoryParameterCreate`.
    """

    description: str | None = None


class PayrollStatutoryParameterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    value: Decimal
    effective_from: date
    effective_to: date | None
    description: str | None
    created_at: datetime
    updated_at: datetime
