import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from eop_api.core.attendance import EventSource, EventType


class AttendanceEventCreate(BaseModel):
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    event_type: EventType
    event_time: datetime
    source: EventSource
    remarks: str | None = Field(default=None, max_length=2000)


class AttendanceEventUpdate(BaseModel):
    """`event_time`/`event_type`/`source`/`remarks`/`employee_id` are
    deliberately absent -- an `AttendanceEvent` is a historical fact and
    must not be mutated in place (AttendanceEvent Integrity workstream).
    `shift_id` (which shift an event is matched against, not what
    happened or when) remains a plain generic-CRUD field. Correcting the
    historical fields uses `AttendanceEventCorrectionRequest` via
    `AttendanceEventService.correct`, not this schema -- `corrects_id`
    correction lineage is never a generic-update field, only ever set by
    that controlled operation.
    """

    shift_id: uuid.UUID | None = None


class AttendanceEventCorrectionRequest(BaseModel):
    """Fields correctable via `POST /hr/attendance-events/{id}/correct`.

    Partial: any field omitted is carried over unchanged from the event
    being corrected. `employee_id`/`shift_id` are deliberately absent --
    a correction always inherits the original event's `employee_id`/
    `shift_id`, so an employee-mismatch case is structurally impossible
    rather than needing a runtime check.
    """

    event_type: EventType | None = None
    event_time: datetime | None = None
    source: EventSource | None = None
    remarks: str | None = Field(default=None, max_length=2000)


class AttendanceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    shift_id: uuid.UUID
    event_type: EventType
    event_time: datetime
    source: EventSource
    remarks: str | None
    corrects_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
