from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.visit import Visit


class CompetitorActivity(BaseEntity):
    """A repeatable competitor observation captured during a `Visit`.
    Field Operations, Competitor Activity Iteration 1.

    Implements the CPO/CTO's D2/D3 decision (repeatable observation):
    `docs/architecture/capabilities/competitor-activity/
    competitor-activity-iteration-1-scope-and-implementation-plan.md`
    §3/§4/§5. One `Visit` may have many `CompetitorActivity` rows -- the
    opposite cardinality from `Survey`'s one-per-`Visit` shape, mirroring
    `Interview`/`Offer`'s own non-unique-FK-to-parent precedent instead.

    `employee_id` is deliberately NOT duplicated onto this entity --
    `CompetitorActivityService` authorizes every operation against the
    resolved parent `Visit` directly, so ownership always reflects
    `Visit.employee_id`'s current value even if it is reassigned after this
    row is created (§6), the identical reasoning already used for `Survey`.
    `visit_id` is `ON DELETE RESTRICT`, matching every other FK into a
    parent aggregate in this repository. No uniqueness constraint --
    deliberate, per the repeatable-observation decision.

    `competitor_name`/`activity_type` are both free-text -- no competitor
    master data, no taxonomy/master-data table, per explicit CPO/CTO
    exclusion.
    """

    __tablename__ = "competitor_activities"
    __table_args__ = (Index("ix_competitor_activities_visit_id", "visit_id"),)

    visit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visits.id", ondelete="RESTRICT"),
    )
    competitor_name: Mapped[str] = mapped_column(String(255))
    activity_type: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)

    visit: Mapped[Visit] = relationship()
