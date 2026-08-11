from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.visit import Visit


class DisplayAudit(BaseEntity):
    """A repeatable display-compliance observation captured during a
    `Visit`. Field Operations, Display Audit Iteration 1.

    Implements the CPO/CTO's D2/D3 decision (repeatable observation):
    `docs/architecture/capabilities/display-audit/
    display-audit-iteration-1-scope-and-implementation-plan.md` §2/§4/§5.
    One `Visit` may have many `DisplayAudit` rows -- the same cardinality
    as `CompetitorActivity`/`PosmAudit`/`VisitPhoto`, the opposite of
    `Survey`'s one-per-`Visit` shape.

    `employee_id` is deliberately NOT duplicated onto this entity --
    `DisplayAuditService` authorizes every operation against the resolved
    parent `Visit` directly, so ownership always reflects
    `Visit.employee_id`'s current value even if it is reassigned after this
    row is created (§6), the identical reasoning already used for `Survey`/
    `CompetitorActivity`/`PosmAudit`/`VisitPhoto`. `visit_id` is `ON DELETE
    RESTRICT`, matching every other FK into a parent aggregate in this
    repository. No uniqueness constraint -- deliberate, per the
    repeatable-observation decision.

    `display_area`/`observation` are both free-text -- no display/product
    master data, no taxonomy/master-data table, per explicit CPO/CTO
    exclusion. No relationship to `Product`/`SKU`, `FileObject`, `Mission`,
    `Survey`, `CompetitorActivity`, or `PosmAudit`.
    """

    __tablename__ = "display_audits"
    __table_args__ = (Index("ix_display_audits_visit_id", "visit_id"),)

    visit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visits.id", ondelete="RESTRICT"),
    )
    display_area: Mapped[str] = mapped_column(String(255))
    observation: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)

    visit: Mapped[Visit] = relationship()
