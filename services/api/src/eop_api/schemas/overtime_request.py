import uuid
from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field


class OvertimeRequestCreate(BaseModel):
    """`status` is deliberately absent -- every new `OvertimeRequest` starts
    `pending`, enforced by `OvertimeRequestService.create`. Subsequent
    `approved`/`rejected` transitions go through `ApprovalService` only,
    never a client-supplied starting value.
    """

    employee_id: uuid.UUID
    overtime_date: date
    start_time: time
    end_time: time
    reason: str | None = Field(default=None, max_length=2000)


class OvertimeRequestUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    overtime_date: date | None = None
    start_time: time | None = None
    end_time: time | None = None
    status: str | None = Field(default=None, min_length=1, max_length=50)
    reason: str | None = Field(default=None, max_length=2000)


class OvertimeRequestRejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=1000)


class OvertimeRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    overtime_date: date
    start_time: time
    end_time: time
    status: str
    reason: str | None
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
