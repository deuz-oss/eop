from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class JobRequisition(BaseEntity):
    """An open position to fill. Recruitment master data, mirroring `Shift`'s
    own global-master-data shape (`code`-unique, plain CRUD).

    `organization_id`/`department_id`/`position_id` mirror `HrEmployee`'s own
    identity-field set exactly -- all required, all `ON DELETE RESTRICT`.

    `status` is a plain, unconstrained string (mirrors `HrEmployee
    .employment_status`), not an enum or state machine -- no recruitment-
    pipeline stage model (screening/interviewing/offered/etc.) is decided or
    invented here (`iteration-1-scope-and-implementation-plan.md` §2).
    """

    __tablename__ = "job_requisitions"
    __table_args__ = (
        UniqueConstraint("code", name="uq_job_requisitions_code"),
        Index("ix_job_requisitions_organization_id", "organization_id"),
        Index("ix_job_requisitions_department_id", "department_id"),
        Index("ix_job_requisitions_position_id", "position_id"),
        Index("ix_job_requisitions_status", "status"),
    )

    code: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(255))
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(String(2000), default=None)
