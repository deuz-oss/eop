from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.visit import Visit


class PosmAudit(BaseEntity):
    """A repeatable POSM (point-of-sale materials) observation captured
    during a `Visit`. Field Operations, POSM Audit Iteration 1.

    Implements the CPO/CTO's D2/D3 decision (repeatable observation):
    `docs/architecture/capabilities/posm-audit/
    posm-audit-iteration-1-scope-and-implementation-plan.md` §2/§3/§4.
    One `Visit` may have many `PosmAudit` rows -- the same cardinality as
    `CompetitorActivity`, the opposite of `Survey`'s one-per-`Visit` shape.

    `employee_id` is deliberately NOT duplicated onto this entity --
    `PosmAuditService` authorizes every operation against the resolved
    parent `Visit` directly, so ownership always reflects
    `Visit.employee_id`'s current value even if it is reassigned after this
    row is created, the identical reasoning already used for `Survey` and
    `CompetitorActivity`. `visit_id` is `ON DELETE RESTRICT`, matching every
    other FK into a parent aggregate in this repository. No uniqueness
    constraint -- deliberate, per the repeatable-observation decision.

    `posm_type`/`condition` are both free-text -- no POSM master data, no
    taxonomy/master-data table, per explicit CPO/CTO exclusion. `condition`
    is observation text only, not a workflow status.
    """

    __tablename__ = "posm_audits"
    __table_args__ = (Index("ix_posm_audits_visit_id", "visit_id"),)

    visit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visits.id", ondelete="RESTRICT"),
    )
    posm_type: Mapped[str] = mapped_column(String(255))
    condition: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)

    visit: Mapped[Visit] = relationship()
