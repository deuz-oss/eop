import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DisplayAuditCreate(BaseModel):
    visit_id: uuid.UUID
    display_area: str = Field(min_length=1, max_length=255)
    observation: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class DisplayAuditUpdate(BaseModel):
    """`visit_id` is deliberately excluded -- immutable after creation
    (`docs/architecture/capabilities/display-audit/
    display-audit-iteration-1-scope-and-implementation-plan.md` §2)."""

    display_area: str | None = Field(default=None, min_length=1, max_length=255)
    observation: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class DisplayAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    display_area: str
    observation: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
