from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.file_object import FileObject
    from eop_api.models.visit import Visit


class VisitPhoto(BaseEntity):
    """One uploaded photo attached to a `Visit`. Field Operations, Photo
    Evidence Iteration 1.

    Implements the CPO/CTO's D1/D3 decision (Visit-only, many-per-Visit
    child aggregate): `docs/architecture/capabilities/photo-evidence/
    photo-evidence-iteration-1-scope-and-implementation-plan.md` §2/§3. One
    `Visit` may have many `VisitPhoto` rows -- the same cardinality as
    `CompetitorActivity`/`PosmAudit`, the opposite of `Survey`'s
    one-per-`Visit` shape. No relationship to `Survey`, `CompetitorActivity`,
    `PosmAudit`, `Mission`, `Store`, or `HrEmployee` directly.

    `employee_id` is deliberately NOT duplicated onto this entity --
    `VisitPhotoService` authorizes every operation against the resolved
    parent `Visit` directly, the identical reasoning already used for
    `Survey`/`CompetitorActivity`/`PosmAudit`. `visit_id` is `ON DELETE
    RESTRICT`, matching every other FK into a parent aggregate in this
    repository. No uniqueness constraint -- deliberate, per the
    repeatable-observation decision.

    `file_object_id` reuses the existing `FileObject` unmodified, `ON
    DELETE RESTRICT` -- mirrors `FieldAttendanceEvent.selfie_file_id`'s
    exact precedent. `FileObject` remains the sole source of file
    metadata (filename, content type, size, storage key, bucket); no
    caption/description/category/tags/coordinates/device-metadata field
    is added here, per explicit CPO/CTO exclusion.
    """

    __tablename__ = "visit_photos"
    __table_args__ = (Index("ix_visit_photos_visit_id", "visit_id"),)

    visit_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("visits.id", ondelete="RESTRICT"),
    )
    file_object_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("file_objects.id", ondelete="RESTRICT"),
    )

    visit: Mapped[Visit] = relationship()
    file_object: Mapped[FileObject] = relationship()
