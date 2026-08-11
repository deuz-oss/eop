import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VisitPhotoCreate(BaseModel):
    visit_id: uuid.UUID
    file_object_id: uuid.UUID


class VisitPhotoUpdate(BaseModel):
    """`visit_id` is deliberately excluded -- immutable after creation,
    mirroring `CompetitorActivityUpdate`/`PosmAuditUpdate` (`docs/
    architecture/capabilities/photo-evidence/
    photo-evidence-iteration-1-scope-and-implementation-plan.md` §3)."""

    file_object_id: uuid.UUID | None = None


class VisitPhotoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    file_object_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
