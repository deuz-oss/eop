from __future__ import annotations

from sqlalchemy import Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class DeductionType(BaseEntity):
    """The catalog of non-statutory deduction categories (D7).

    Global HR/Payroll reference data, mirroring `EmploymentType`/`JobGrade`
    exactly (`models/employment_type.py`): `code` globally unique, no
    hierarchy, no scoping to any other entity. Owned by Payroll, per the
    already-decided exclusion (`compensation/decision.md` §4: "Deduction...
    Belongs to Payroll Calculation / Payroll Run").

    No write API route is exposed for this entity in v1
    (`docs/architecture/capabilities/payroll-calculation/
    implementation-plan.md` §10.4): no RBAC/permission-actor concept exists
    anywhere in this codebase for admin/reference-data writes
    (`TECHNICAL_DEBT_REGISTER.md` TD-004). The model/repository/service are
    fully built and tested; rows are seeded/managed directly until an admin
    authorization concept exists.
    """

    __tablename__ = "deduction_types"
    __table_args__ = (
        UniqueConstraint("code", name="uq_deduction_types_code"),
        Index("ix_deduction_types_name", "name"),
    )

    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(1000), default=None)
