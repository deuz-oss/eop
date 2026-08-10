from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.hr_employee import HrEmployee
    from eop_api.models.store import Store


class Mission(BaseEntity):
    """A planning/assignment record: one employee assigned to one store on
    one date. Field Operations, Mission Iteration 1.

    Deliberately minimal, flat CRUD -- no status/lifecycle, no GPS/photo,
    no Route/Route Stop/Territory reference, no Visit reference
    (`docs/architecture/capabilities/mission/
    mission-iteration-1-scope-and-implementation-plan.md` §3/§4/§5).
    Distinct from `Visit`: Mission is the *plan* (assigned in advance by an
    administrator), `Visit` is the *executed* record of a field employee
    actually being at a store -- no structural or FK link between them.

    Both `employee_id` and `store_id` are `ON DELETE RESTRICT`, matching
    every other FK into `HrEmployee`/`Store` in this repository -- planning
    history must be preserved, not silently cascaded away. No uniqueness
    constraint -- mirrors `Visit`'s own precedent exactly: two assignments
    for the same employee/store/date are not contradictory (unlike
    `Target`'s single-authoritative-goal-value semantics), so duplicates are
    expected and permitted, not prevented.
    """

    __tablename__ = "missions"
    __table_args__ = (
        Index("ix_missions_employee_id", "employee_id"),
        Index("ix_missions_store_id", "store_id"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"),
    )
    store_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("stores.id", ondelete="RESTRICT"),
    )
    scheduled_date: Mapped[date] = mapped_column(Date)

    employee: Mapped[HrEmployee] = relationship()
    store: Mapped[Store] = relationship()
