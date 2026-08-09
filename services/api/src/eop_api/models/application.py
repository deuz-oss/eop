from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, UniqueConstraint
from sqlalchemy import Enum as SqlEnum
from sqlalchemy.orm import Mapped, mapped_column

from eop_api.core.recruitment import ApplicationStatus
from eop_api.db.base import BaseEntity


class Application(BaseEntity):
    """Links a `Candidate` to a `JobRequisition`. Peer-association aggregate,
    mirroring `Assignment` (Project Tracking's `Employee`<->`Project` link)
    exactly: two FKs to independently-owned aggregates, its own payload,
    pair-uniqueness. `ON DELETE RESTRICT` (not `Assignment`'s own outlier
    `CASCADE`) -- the now-dominant repository convention
    (`iteration-1-scope-and-implementation-plan.md` §2).

    `status` (`ApplicationStatus`) is Recruitment Iteration 2's lifecycle
    boundary, decided in `docs/architecture/capabilities/recruitment/
    iteration-2-business-decision-package.md` (Approved, D1) -- mirrors
    `PayrollRun.status`'s exact column shape (`SqlEnum(..., native_enum=
    False)`). New applications always start `APPLIED`
    (`ApplicationService.create`); every other transition is validated
    against `VALID_APPLICATION_TRANSITIONS` (`core/recruitment.py`) by
    `ApplicationService.transition`, never by a generic field update.
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
    status: Mapped[ApplicationStatus] = mapped_column(
        SqlEnum(ApplicationStatus, name="application_status", native_enum=False, length=20),
        default=ApplicationStatus.APPLIED,
    )
    applied_date: Mapped[date] = mapped_column(Date)
