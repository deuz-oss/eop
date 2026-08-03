from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class LeaveBalance(BaseEntity):
    """The leave balance allocated to one employee for one leave period.

    Deliberately persistence-shaped, not calculation/ledger shaped: each row
    just holds `allocated_days`, `used_days`, and `remaining_days` as plain
    stored values for one HrEmployee and one `period_year`. Accrual,
    deduction, carry-forward, expiration, and synchronization with
    LeaveRequest are all future concerns -- out of scope here.

    `employee_id` is `ON DELETE RESTRICT`, matching every other FK into
    `HrEmployee` from HR data: leave balance history must be preserved, not
    silently cascaded away.
    """

    __tablename__ = "leave_balances"
    __table_args__ = (
        Index("ix_leave_balances_employee_id", "employee_id"),
        Index("ix_leave_balances_period_year", "period_year"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    period_year: Mapped[int] = mapped_column(Integer)
    allocated_days: Mapped[int] = mapped_column(Integer, default=0)
    used_days: Mapped[int] = mapped_column(Integer, default=0)
    remaining_days: Mapped[int] = mapped_column(Integer, default=0)
