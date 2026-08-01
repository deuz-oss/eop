import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    content_type: str
    size: int
    bucket: str
    storage_key: str
    created_at: datetime
