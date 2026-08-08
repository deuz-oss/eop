import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CompensationCreate(BaseModel):
    """`corrects_id` set only to create a compensating correction
    (`docs/architecture/capabilities/compensation/decision.md` §19,
    Option C2b) referencing the Compensation row being corrected. `None`
    (default) creates an ordinary row, subject to the normal overlap
    prohibition (O1).
    """

    employee_id: uuid.UUID
    base_salary_amount: Decimal
    base_salary_currency: str
    effective_from: date
    effective_to: date | None = None
    corrects_id: uuid.UUID | None = None


class CompensationUpdate(BaseModel):
    """Only `is_active` is updatable.

    `base_salary_amount`/`base_salary_currency`/`effective_from`/
    `effective_to`/`corrects_id` are deliberately absent: changing them on
    an existing row would mutate a historical business fact in place,
    which `docs/architecture/capabilities/compensation/decision.md`
    §7/§17 (Accepted) prohibit. Recording a new compensation state, or a
    correction, uses `CompensationCreate`, not this schema.
    """

    is_active: bool | None = None


class CompensationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_id: uuid.UUID
    base_salary_amount: Decimal
    base_salary_currency: str
    effective_from: date
    effective_to: date | None
    corrects_id: uuid.UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
