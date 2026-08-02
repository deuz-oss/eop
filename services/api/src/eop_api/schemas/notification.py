import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class Notification(BaseModel):
    """A sent notification.

    Deliberately minimal -- no status, delivery metadata, retry
    information, or channel. This PR only establishes that a notification
    was sent, not how or whether it was delivered.
    """

    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    recipient: str
    subject: str
    body: str
    created_at: datetime
