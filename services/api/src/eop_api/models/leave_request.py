from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class LeaveRequest(BaseEntity):
    """A single employee's request to be away for a dated span.

    Deliberately request-shaped, not balance/entitlement/ledger shaped: each
    row is one ask, covering one contiguous date span, for one HrEmployee.
    Leave type, balance, entitlement, approval workflow, and attendance
    reconciliation are all future concerns -- out of scope here.

    `employee_id` is `ON DELETE RESTRICT`, matching every other FK into
    `HrEmployee` from HR data: leave history must be preserved, not silently
    cascaded away.

    `status` is intentionally a plain string column, storage only -- the same
    style already used by `Project.status`/`Task.status`. No enum, no CHECK
    constraint, no transition validation: approval workflow is a future PR's
    concern, not this one's.
    """

    __tablename__ = "leave_requests"
    __table_args__ = (
        Index("ix_leave_requests_employee_id", "employee_id"),
        Index("ix_leave_requests_status", "status"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    # Storage only -- no transition validation. Approval workflow is intentionally
    # deferred to a future PR.
    status: Mapped[str] = mapped_column(String(50), default="pending")
    reason: Mapped[str | None] = mapped_column(String(2000), default=None)
