import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class PerformanceReviewCreate(BaseModel):
    employee_id: uuid.UUID
    review_period_start: date
    review_period_end: date
    notes: str | None = Field(default=None, max_length=2000)


class PerformanceReviewUpdate(BaseModel):
    employee_id: uuid.UUID | None = None
    review_period_start: date | None = None
    review_period_end: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


class PerformanceReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    review_period_start: date
    review_period_end: date
    notes: str | None
    created_at: datetime
    updated_at: datetime
