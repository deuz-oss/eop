import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CompensationCreate(BaseModel):
    employee_id: uuid.UUID
    base_salary_amount: Decimal
    base_salary_currency: str
    effective_from: date


class CompensationUpdate(BaseModel):
    base_salary_amount: Decimal | None = None
    base_salary_currency: str | None = None
    effective_from: date | None = None
    is_active: bool | None = None


class CompensationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    base_salary_amount: Decimal
    base_salary_currency: str
    effective_from: date
    is_active: bool
    created_at: datetime
    updated_at: datetime
