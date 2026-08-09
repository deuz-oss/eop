from __future__ import annotations

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Kpi(BaseEntity):
    """Definition-only master data describing a named performance indicator
    (e.g. "Visit Compliance Rate"). Performance Management, KPI Iteration 1.

    Represents only the indicator's identity -- not a value, an assignment,
    a target, an achievement, or a calculation
    (`docs/architecture/capabilities/performance/
    kpi-iteration-1-scope-and-implementation-plan.md` §3/§7). `unit` is a
    free-text label (e.g. "%", "visits/day"), not a fixed enum -- no closed
    unit taxonomy is named anywhere in product scope, mirroring
    `StoreType`'s own free-form-over-fixed-enum resolution for the same
    reason (§4).

    No relationships, no foreign keys, no organization/employee scope --
    global, admin-managed reference data, mirroring `JobGrade`/
    `EmploymentType`/`StoreType` exactly.
    """

    __tablename__ = "kpis"
    __table_args__ = (
        UniqueConstraint("code", name="uq_kpis_code"),
        Index("ix_kpis_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(100), default=None)
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
