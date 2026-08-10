import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AchievementCreate(BaseModel):
    target_id: uuid.UUID
    actual_value: Decimal


class AchievementUpdate(BaseModel):
    """`target_id` is deliberately excluded -- immutable after creation, it
    is the row's identity (`docs/architecture/capabilities/performance/
    achievement-iteration-1-scope-and-implementation-plan.md` §6). Only
    `actual_value` may change."""

    actual_value: Decimal | None = None


class AchievementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_id: uuid.UUID
    actual_value: Decimal
    created_at: datetime
    updated_at: datetime
