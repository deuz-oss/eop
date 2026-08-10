import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PosmAuditCreate(BaseModel):
    visit_id: uuid.UUID
    posm_type: str = Field(min_length=1, max_length=255)
    condition: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class PosmAuditUpdate(BaseModel):
    """`visit_id` is deliberately excluded -- immutable after creation
    (`docs/architecture/capabilities/posm-audit/
    posm-audit-iteration-1-scope-and-implementation-plan.md` §2)."""

    posm_type: str | None = Field(default=None, min_length=1, max_length=255)
    condition: str | None = Field(default=None, min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class PosmAuditResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    posm_type: str
    condition: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
