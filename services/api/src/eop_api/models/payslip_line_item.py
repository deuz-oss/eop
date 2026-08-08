from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Enum as SqlEnum
from sqlalchemy import ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.core.payroll import PayslipLineItemType
from eop_api.db.base import BaseEntity


class PayslipLineItem(BaseEntity):
    """One component (earning or deduction) of a `Payslip`'s structured result (E1).

    `payslip_id` uses `ON DELETE CASCADE` -- a deliberate departure from
    the `RESTRICT` convention used everywhere else in this codebase. A line
    item has no independent identity or meaning apart from its parent
    `Payslip` (the same "owned child, no independent existence" shape
    `payslip/discovery.md` §9 identified in the `Task`/`Assignment`
    `CASCADE` precedent, as distinct from `Payslip`'s own `RESTRICT`
    relationship to `PayrollRun`, where `Payslip` *does* have independent
    identity). Not declared as an ORM `relationship()` on `Payslip` --
    `PayslipService` fetches/attaches line items explicitly via
    `PayslipLineItemRepository`, avoiding async-session lazy-load/expunge
    complexity.

    `line_amount` is always stored **unsigned** (positive). Earning vs.
    deduction is determined entirely by `component_type`
    (`core/payroll.py`'s `EARNING_LINE_ITEM_TYPES`/`DEDUCTION_LINE_ITEM_TYPES`),
    never by sign.

    `source_id` is an untyped, unconstrained reference (e.g. an
    `Allowance.id`, `Deduction.id`, or `Compensation.id` this line item
    derives from), for traceability only -- no FK, since it may point to
    different tables depending on `component_type` and no polymorphic-FK
    precedent exists anywhere in this repository.
    """

    __tablename__ = "payslip_line_items"
    __table_args__ = (Index("ix_payslip_line_items_payslip_id", "payslip_id"),)

    payslip_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payslips.id", ondelete="CASCADE"),
    )
    component_type: Mapped[PayslipLineItemType] = mapped_column(
        SqlEnum(PayslipLineItemType, name="payslip_line_item_type", native_enum=False, length=30),
    )
    label: Mapped[str] = mapped_column(String(255))
    line_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    line_currency: Mapped[str] = mapped_column(String(3))
    source_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
