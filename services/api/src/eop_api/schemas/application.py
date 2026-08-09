import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict

from eop_api.core.recruitment import ApplicationStatus


class ApplicationCreate(BaseModel):
    """`status` is deliberately absent -- every new `Application` starts
    `APPLIED` (`core/recruitment.py`'s transition graph has no incoming
    edge into any other stage), enforced by `ApplicationService.create`.
    Subsequent stage changes go through `ApplicationService.transition`
    only, never a client-supplied starting value.
    """

    candidate_id: uuid.UUID
    job_requisition_id: uuid.UUID
    applied_date: date


class ApplicationUpdate(BaseModel):
    """`status` is deliberately absent, mirroring `PayrollRunUpdate`'s
    exclusion of `status` -- lifecycle changes go through
    `ApplicationService.transition` (and the dedicated `/transition` route)
    only, never a generic field update.
    """

    candidate_id: uuid.UUID | None = None
    job_requisition_id: uuid.UUID | None = None
    applied_date: date | None = None


class ApplicationTransitionRequest(BaseModel):
    status: ApplicationStatus


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    candidate_id: uuid.UUID
    job_requisition_id: uuid.UUID
    status: ApplicationStatus
    applied_date: date
    created_at: datetime
    updated_at: datetime
