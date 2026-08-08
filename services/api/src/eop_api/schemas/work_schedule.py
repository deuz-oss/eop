import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class WorkScheduleCreate(BaseModel):
    """`corrects_id` set only to create a compensating correction (mirrors
    `CompensationCreate`'s exact pattern) referencing the WorkSchedule row
    being corrected. `None` (default) creates an ordinary row, subject to
    the normal overlap prohibition.

    All seven `works_*` fields are required, not defaulted -- no work-week
    pattern (e.g. Monday-Friday) is assumed as a business default; the
    caller must state every day explicitly.
    """

    employee_id: uuid.UUID
    shift_id: uuid.UUID
    works_monday: bool
    works_tuesday: bool
    works_wednesday: bool
    works_thursday: bool
    works_friday: bool
    works_saturday: bool
    works_sunday: bool
    effective_from: date
    effective_to: date | None = None
    corrects_id: uuid.UUID | None = None


class WorkScheduleUpdate(BaseModel):
    """Only `is_active` is updatable.

    Changing `shift_id`, any `works_*` field, or the effective period on an
    existing row would mutate a historical business fact in place -- mirrors
    `CompensationUpdate`'s exact restriction. Recording a new schedule state,
    or a correction, uses `WorkScheduleCreate`, not this schema.
    """

    is_active: bool | None = None


class WorkScheduleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    works_monday: bool
    works_tuesday: bool
    works_wednesday: bool
    works_thursday: bool
    works_friday: bool
    works_saturday: bool
    works_sunday: bool
    effective_from: date
    effective_to: date | None
    corrects_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
