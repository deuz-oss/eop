import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TargetCreate(BaseModel):
    kpi_id: uuid.UUID
    employee_id: uuid.UUID
    period_year: int
    period_month: int = Field(ge=1, le=12)
    goal_value: Decimal


class TargetUpdate(BaseModel):
    """`kpi_id`/`employee_id`/`period_year`/`period_month` are deliberately
    excluded -- immutable after creation, since together they form the
    row's identity and uniqueness key (`docs/architecture/capabilities/
    performance/target-iteration-1-scope-and-implementation-plan.md` §14).
    Only `goal_value` may change."""

    goal_value: Decimal | None = None


class TargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kpi_id: uuid.UUID
    employee_id: uuid.UUID
    period_year: int
    period_month: int
    goal_value: Decimal
    created_at: datetime
    updated_at: datetime
