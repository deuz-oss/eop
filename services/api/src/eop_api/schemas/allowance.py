import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AllowanceCreate(BaseModel):
    """`corrects_id` set only to create a compensating correction
    (mirrors `CompensationCreate`). `None` (default) creates an ordinary
    row, subject to the normal overlap prohibition scoped to
    `(employee_id, allowance_type)`.
    """

    employee_id: uuid.UUID
    allowance_type: str
    allowance_amount: Decimal
    allowance_currency: str
    effective_from: date
    effective_to: date | None = None
    corrects_id: uuid.UUID | None = None


class AllowanceUpdate(BaseModel):
    """Only `is_active` is updatable -- mirrors `CompensationUpdate` exactly."""

    is_active: bool | None = None


class AllowanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    allowance_type: str
    allowance_amount: Decimal
    allowance_currency: str
    effective_from: date
    effective_to: date | None
    corrects_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
