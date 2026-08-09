from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.db.base import BaseEntity


class Application(BaseEntity):
    """Links a `Candidate` to a `JobRequisition`. Peer-association aggregate,
    mirroring `Assignment` (Project Tracking's `Employee`<->`Project` link)
    exactly: two FKs to independently-owned aggregates, its own payload,
    pair-uniqueness. `ON DELETE RESTRICT` (not `Assignment`'s own outlier
    `CASCADE`) -- the now-dominant repository convention
    (`iteration-1-scope-and-implementation-plan.md` §2).

    `status` is a plain, unconstrained string, same rationale as
    `JobRequisition.status` -- no pipeline/stage model is decided here.
    """

    __tablename__ = "applications"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_requisition_id",
            name="uq_applications_candidate_id_job_requisition_id",
        ),
        Index("ix_applications_candidate_id", "candidate_id"),
        Index("ix_applications_job_requisition_id", "job_requisition_id"),
        Index("ix_applications_status", "status"),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("candidates.id", ondelete="RESTRICT"),
    )
    job_requisition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_requisitions.id", ondelete="RESTRICT"),
    )
    status: Mapped[str] = mapped_column(String(50))
    applied_date: Mapped[date] = mapped_column(Date)
