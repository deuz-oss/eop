import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LeaveBalanceCreate(BaseModel):
    """`used_days`/`remaining_days` are deliberately absent -- every new
    `LeaveBalance` starts with `used_days=0` and `remaining_days=allocated_days`,
    enforced by `LeaveBalanceService.create`. Subsequent deductions go through
    `ApprovalService._sync_leave_balance` only, never a client-supplied
    starting value.
    """

    employee_id: uuid.UUID
    period_year: int
    allocated_days: int = 0


class LeaveBalanceUpdate(BaseModel):
    """`used_days`/`remaining_days` are deliberately absent, mirroring
    `LeaveBalanceCreate` -- they are controlled exclusively by
    `ApprovalService._sync_leave_balance`. `allocated_days` remains a plain
    generic-CRUD field (admin/HR allocation data); changing it recomputes
    `remaining_days` against the persisted `used_days` server-side, so the
    `remaining_days = allocated_days - used_days` invariant always holds
    after this call.
    """

    employee_id: uuid.UUID | None = None
    period_year: int | None = None
    allocated_days: int | None = None


class LeaveBalanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    period_year: int
    allocated_days: int
    used_days: int
    remaining_days: int
    created_at: datetime
    updated_at: datetime
