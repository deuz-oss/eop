import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from eop_api.core.payroll import PayslipLineItemType


class PayslipLineItemCreate(BaseModel):
    """Internal-only: built by `PayrollCalculationService`'s calculator
    components and passed to `PayslipService.create`, never accepted
    directly from the public `POST /payslips` route (`PayslipCreate`
    remains unchanged)."""

    component_type: PayslipLineItemType
    label: str
    line_amount: Decimal
    line_currency: str
    source_id: uuid.UUID | None = None


class PayslipLineItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    payslip_id: uuid.UUID
    component_type: PayslipLineItemType
    label: str
    line_amount: Decimal
    line_currency: str
    source_id: uuid.UUID | None
    created_at: datetime
