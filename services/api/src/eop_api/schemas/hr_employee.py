import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class EmployeeCreate(BaseModel):
    employee_number: str = Field(min_length=1, max_length=50)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    organization_id: uuid.UUID
    department_id: uuid.UUID
    position_id: uuid.UUID
    team_id: uuid.UUID
    location_id: uuid.UUID
    manager_id: uuid.UUID | None = None
    job_grade_id: uuid.UUID
    hire_date: date
    employment_status: str = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)


class EmployeeUpdate(BaseModel):
    employee_number: str | None = Field(default=None, min_length=1, max_length=50)
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    organization_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    position_id: uuid.UUID | None = None
    team_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    manager_id: uuid.UUID | None = None
    job_grade_id: uuid.UUID | None = None
    hire_date: date | None = None
    employment_status: str | None = Field(default=None, min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=2000)


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    employee_number: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: str | None
    organization_id: uuid.UUID
    department_id: uuid.UUID
    position_id: uuid.UUID
    team_id: uuid.UUID
    location_id: uuid.UUID
    manager_id: uuid.UUID | None
    job_grade_id: uuid.UUID
    hire_date: date
    employment_status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
