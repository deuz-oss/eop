import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from eop_api.schemas.payslip_line_item import PayslipLineItemResponse


class PayslipCreate(BaseModel):
    employee_id: uuid.UUID
    payroll_run_id: uuid.UUID
    gross_salary_amount: Decimal
    gross_salary_currency: str
    net_salary_amount: Decimal
    net_salary_currency: str


class PayslipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    payroll_run_id: uuid.UUID
    gross_salary_amount: Decimal | None
    gross_salary_currency: str | None
    net_salary_amount: Decimal | None
    net_salary_currency: str | None
    line_items: list[PayslipLineItemResponse] = []
    created_at: datetime
    updated_at: datetime
