import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from eop_api.core.field_attendance import FieldAttendanceEventType


class FieldAttendanceEventCreate(BaseModel):
    employee_id: uuid.UUID
    event_type: FieldAttendanceEventType
    event_time: datetime
    latitude: Decimal = Field(ge=-90, le=90)
    longitude: Decimal = Field(ge=-180, le=180)
    gps_accuracy_meters: Decimal = Field(ge=0)
    selfie_file_id: uuid.UUID


class FieldAttendanceEventUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    event_type: FieldAttendanceEventType | None = None
    event_time: datetime | None = None
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)
    gps_accuracy_meters: Decimal | None = Field(default=None, ge=0)
    selfie_file_id: uuid.UUID | None = None


class FieldAttendanceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    event_type: FieldAttendanceEventType
    event_time: datetime
    latitude: Decimal
    longitude: Decimal
    gps_accuracy_meters: Decimal
    selfie_file_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
