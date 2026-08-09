from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.visit import Visit


class Survey(BaseEntity):
    """A fixed, three-question operational survey attached to one `Visit`.
    Field Operations, Survey Iteration 1.

    Implements the CPO/CTO's D1/D2 decision (Fixed Question Set):
    `docs/architecture/capabilities/survey/
    iteration-1-scope-and-implementation-plan.md` §1/§2/§3. Each of the
    three fixed questions is its own required `Boolean` column -- no
    generic question/answer table, no questionnaire engine, no runtime
    question configuration.

    One Survey per Visit: `visit_id` is `UniqueConstraint`-enforced, not a
    business-layer convention alone (§4). `employee_id` is deliberately
    NOT duplicated onto this entity -- `SurveyService` authorizes every
    operation against the resolved parent `Visit` directly, so ownership
    always reflects `Visit.employee_id`'s current value even if it is
    reassigned after the Survey is created (§5). `visit_id` is
    `ON DELETE RESTRICT`, matching every other FK into a parent aggregate
    in this repository.
    """

    __tablename__ = "surveys"
    __table_args__ = (UniqueConstraint("visit_id", name="uq_surveys_visit_id"),)

    visit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visits.id", ondelete="RESTRICT"),
    )
    display_compliant: Mapped[bool] = mapped_column(Boolean)
    stock_available: Mapped[bool] = mapped_column(Boolean)
    posm_available: Mapped[bool] = mapped_column(Boolean)

    visit: Mapped[Visit] = relationship()
