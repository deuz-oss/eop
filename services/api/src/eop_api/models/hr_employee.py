from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from eop_api.db.base import BaseEntity

if TYPE_CHECKING:
    from eop_api.models.department import Department
    from eop_api.models.location import Location
    from eop_api.models.organization import Organization
    from eop_api.models.position import Position
    from eop_api.models.team import Team


class HrEmployee(BaseEntity):
    """HR master data for a person, scoped to the HR bounded context.

    Deliberately independent from the Project Tracking `Employee` (a
    different, pre-existing entity used by `Assignment`/`Task`): the two
    model different concepts under the same business word "Employee" and
    share no foreign key relationship. `organization_id`, `department_id`,
    `position_id`, `team_id`, and `location_id` are all `ON DELETE RESTRICT`
    -- this is master data, so deleting any of those while an HrEmployee
    still references it must fail at the database level rather than
    silently cascading. `manager_id` is a nullable self-reference, also
    `RESTRICT`; only a direct self-manager is rejected (in `HrEmployeeService`)
    -- no recursive validation or cycle detection across the tree.
    """

    __tablename__ = "hr_employees"
    __table_args__ = (
        UniqueConstraint("employee_number", name="uq_hr_employees_employee_number"),
        UniqueConstraint("email", name="uq_hr_employees_email"),
        Index("ix_hr_employees_organization_id", "organization_id"),
        Index("ix_hr_employees_department_id", "department_id"),
        Index("ix_hr_employees_position_id", "position_id"),
        Index("ix_hr_employees_team_id", "team_id"),
        Index("ix_hr_employees_location_id", "location_id"),
        Index("ix_hr_employees_manager_id", "manager_id"),
        Index("ix_hr_employees_employment_status", "employment_status"),
        Index("ix_hr_employees_full_name", "full_name"),
        Index("ix_hr_employees_job_grade_id", "job_grade_id"),
        Index("ix_hr_employees_employment_type_id", "employment_type_id"),
        Index("ix_hr_employees_employment_status_id", "employment_status_id"),
        Index("ix_hr_employees_shift_id", "shift_id"),
    )

    employee_number: Mapped[str] = mapped_column(String(50))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    full_name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50), default=None)

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
    )
    department_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT"),
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="RESTRICT"),
    )
    location_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("locations.id", ondelete="RESTRICT"),
    )
    manager_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hr_employees.id", ondelete="RESTRICT"), default=None
    )
    job_grade_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("job_grades.id", ondelete="RESTRICT"),
    )
    employment_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employment_types.id", ondelete="RESTRICT"),
    )
    employment_status_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employment_statuses.id", ondelete="RESTRICT"),
    )
    shift_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shifts.id", ondelete="RESTRICT"),
    )

    hire_date: Mapped[date] = mapped_column(Date)
    employment_status: Mapped[str] = mapped_column(String(50))

    notes: Mapped[str | None] = mapped_column(String(2000), default=None)

    organization: Mapped[Organization] = relationship()
    department: Mapped[Department] = relationship()
    position: Mapped[Position] = relationship()
    team: Mapped[Team] = relationship()
    location: Mapped[Location] = relationship()
    manager: Mapped[HrEmployee | None] = relationship(remote_side="HrEmployee.id")
