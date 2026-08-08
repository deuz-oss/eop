from __future__ import annotations

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class PayrollRun(BaseEntity):
    """The Payroll bounded context's aggregate root (iteration 1: structural scaffolding only).

    Deliberately not employee-scoped -- that role belongs to a future
    `Payslip` aggregate, not to `PayrollRun` itself, per
    `docs/architecture/capabilities/payroll/decision.md` §2-3 and §6.
    `code` is globally unique, `name` is a paired human-readable label,
    matching the identity shape already used by `EmploymentType`/
    `EmploymentStatus`/`JobGrade`/`Shift`/`Holiday`. No period, status,
    monetary, or relationship field exists on this entity: payroll
    calculation, processing, authorization, and integration are all future,
    separate capabilities, per
    `docs/architecture/capabilities/payroll/implementation-plan.md`.
    """

    __tablename__ = "payroll_runs"
    __table_args__ = (
        UniqueConstraint("code", name="uq_payroll_runs_code"),
        Index("ix_payroll_runs_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
