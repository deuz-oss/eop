import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from eop_api.core.payroll import PayrollRunStatus


class PayrollRunCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    period_start: date
    period_end: date
    currency: str = Field(min_length=1, max_length=3)


class PayrollRunUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)


class PayrollRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    status: PayrollRunStatus
    period_start: date | None
    period_end: date | None
    currency: str | None
    created_at: datetime
    updated_at: datetime
