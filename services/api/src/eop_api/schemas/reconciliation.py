import uuid
from datetime import date

from pydantic import BaseModel


class AttendanceReconciliationResponse(BaseModel):
    employee_id: uuid.UUID
    date: date
    status: str
