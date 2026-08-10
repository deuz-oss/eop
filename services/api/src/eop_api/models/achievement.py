from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.target import Target


class Achievement(BaseEntity):
    """The manually recorded actual value achieved against one `Target`.
    Performance Management, Achievement Iteration 1.

    Achievement Iteration 1 is a manually entered actual value against
    exactly one Target. Automatic/computed achievement is deferred
    (`docs/architecture/capabilities/performance/
    achievement-iteration-1-scope-and-implementation-plan.md` §3 D3, §10).

    `target_id` is the sole relationship -- `employee_id`/`kpi_id`/
    `period_year`/`period_month` are deliberately not duplicated here; they
    are read through `Achievement.target` (§4/§7). `ON DELETE RESTRICT`
    matches every other FK in this repository into a row that must be
    preserved as history.

    At most one `Achievement` may exist per `Target`, enforced at the
    database level via a unique `target_id` (§6), mirroring `Survey.visit_id`'s
    identical one-per-parent `UniqueConstraint` precedent.

    `actual_value` is `Numeric(18, 6)`, mirroring `Target.goal_value`'s
    precedent exactly -- a generic, non-monetary numeric value. No `unit`
    column: it is inherited conceptually through `Achievement.target.kpi.unit`,
    never duplicated (§9).
    """

    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("target_id", name="uq_achievements_target_id"),)

    target_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("targets.id", ondelete="RESTRICT"),
    )
    actual_value: Mapped[Decimal] = mapped_column(Numeric(18, 6))

    target: Mapped[Target] = relationship()
