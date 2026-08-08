import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DeductionCreate(BaseModel):
    employee_id: uuid.UUID
    deduction_type_id: uuid.UUID
    payroll_run_id: uuid.UUID
    deduction_amount: Decimal
    deduction_currency: str
    note: str | None = None


class DeductionUpdate(BaseModel):
    deduction_amount: Decimal | None = None
    deduction_currency: str | None = None
    note: str | None = None


class DeductionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    deduction_type_id: uuid.UUID
    payroll_run_id: uuid.UUID
    deduction_amount: Decimal
    deduction_currency: str
    note: str | None
    created_at: datetime
    updated_at: datetime
