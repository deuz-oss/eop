import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SurveyCreate(BaseModel):
    visit_id: uuid.UUID
    display_compliant: bool
    stock_available: bool
    posm_available: bool


class SurveyUpdate(BaseModel):
    """`visit_id` is deliberately excluded -- immutable after creation
    (`docs/architecture/capabilities/survey/
    iteration-1-scope-and-implementation-plan.md` §6)."""

    display_compliant: bool | None = None
    stock_available: bool | None = None
    posm_available: bool | None = None


class SurveyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    display_compliant: bool
    stock_available: bool
    posm_available: bool
    created_at: datetime
    updated_at: datetime
