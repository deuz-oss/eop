import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CompetitorActivityCreate(BaseModel):
    visit_id: uuid.UUID
    competitor_name: str = Field(min_length=1, max_length=255)
    activity_type: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class CompetitorActivityUpdate(BaseModel):
    """`visit_id` is deliberately excluded -- immutable after creation
    (`docs/architecture/capabilities/competitor-activity/
    competitor-activity-iteration-1-scope-and-implementation-plan.md`
    §6)."""

    competitor_name: str | None = Field(default=None, min_length=1, max_length=255)
    activity_type: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class CompetitorActivityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    competitor_name: str
    activity_type: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
