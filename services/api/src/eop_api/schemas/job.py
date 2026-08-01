import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class Job(BaseModel):
    """A queued unit of background work.

    Deliberately minimal -- no status, retries, progress, or execution
    metadata. This PR only establishes that a job was queued, not that
    anything runs it.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    name: str
    payload: dict[str, Any]
    queued_at: datetime
