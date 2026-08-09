from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.hr_employee import HrEmployee
    from eop_api.models.store import Store


class Visit(BaseEntity):
    """A field employee's visit to a `Store`. Field Operations, Visit Iteration 1.

    Deliberately minimal, flat CRUD -- no status/lifecycle, no GPS/photo/
    check-in-out, no Survey/Competitor Activity/Display Audit/Stock Check/
    POSM Audit, no Mission reference (`docs/architecture/capabilities/visit/
    iteration-1-scope-and-implementation-plan.md` §2/§3/§5/§7). Distinct
    from `AttendanceEvent` (HR shift clock-in/out) despite the shared word
    "Attendance" in product scope -- neither reused nor modified (§1).

    Both `employee_id` and `store_id` are `ON DELETE RESTRICT` -- visit
    history must be preserved, not silently cascaded away, matching every
    other FK into `HrEmployee`/master data in this repository. No
    uniqueness constraint -- multiple visits per employee/store over time
    are expected and normal.
    """

    __tablename__ = "visits"
    __table_args__ = (
        Index("ix_visits_employee_id", "employee_id"),
        Index("ix_visits_store_id", "store_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"),
    )
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)

    employee: Mapped[HrEmployee] = relationship()
    store: Mapped[Store] = relationship()
