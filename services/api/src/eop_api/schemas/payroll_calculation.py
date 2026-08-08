import uuid

from pydantic import BaseModel


class PayrollCalculationRequest(BaseModel):
    payroll_run_id: uuid.UUID
    employee_id: uuid.UUID
