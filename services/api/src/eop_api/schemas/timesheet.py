import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class TimesheetCreate(BaseModel):
    """`status` is deliberately absent -- every new `Timesheet` starts
    `pending`, enforced by `TimesheetService.create`. Subsequent
    `approved`/`rejected` transitions go through `ApprovalService` only,
    never a client-supplied starting value.
    """

    employee_id: uuid.UUID
    start_date: date
    end_date: date


class TimesheetUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)


class TimesheetRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class TimesheetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    start_date: date
    end_date: date
    status: str
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
