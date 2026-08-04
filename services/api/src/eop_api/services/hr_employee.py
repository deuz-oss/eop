import uuid
from collections.abc import Callable, Sequence

from eop_api.exceptions.department import DepartmentOrganizationMismatchError
from eop_api.models.hr_employee import HrEmployee
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.employment_status import EmploymentStatusRepository
from eop_api.repositories.employment_type import EmploymentTypeRepository
from eop_api.repositories.hr_employee import HrEmployeeRepository
from eop_api.repositories.job_grade import JobGradeRepository
from eop_api.repositories.location import LocationRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.position import PositionRepository
from eop_api.repositories.shift import ShiftRepository
from eop_api.repositories.team import TeamRepository
from eop_api.repositories.user import UserRepository
from eop_api.schemas.hr_employee import EmployeeCreate, EmployeeUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class OrganizationNotFoundError(Exception):
    """Raised when the organization referenced by an HrEmployee does not exist.

    Local to the HrEmployee module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class DepartmentNotFoundError(Exception):
    """Raised when the department referenced by an HrEmployee does not exist."""


class PositionNotFoundError(Exception):
    """Raised when the position referenced by an HrEmployee does not exist."""


class PositionOrganizationMismatchError(Exception):
    """Raised when an HrEmployee's position belongs to a different organization."""


class TeamNotFoundError(Exception):
    """Raised when the team referenced by an HrEmployee does not exist."""


class TeamOrganizationMismatchError(Exception):
    """Raised when an HrEmployee's team belongs to a different organization."""


class TeamDepartmentMismatchError(Exception):
    """Raised when an HrEmployee's team belongs to a different department."""


class LocationNotFoundError(Exception):
    """Raised when the location referenced by an HrEmployee does not exist."""


class JobGradeNotFoundError(Exception):
    """Raised when the job grade referenced by an HrEmployee does not exist."""


class EmploymentTypeNotFoundError(Exception):
    """Raised when the employment type referenced by an HrEmployee does not exist."""


class EmploymentStatusNotFoundError(Exception):
    """Raised when the employment status referenced by an HrEmployee does not exist."""


class ShiftNotFoundError(Exception):
    """Raised when the shift referenced by an HrEmployee does not exist."""


class UserNotFoundError(Exception):
    """Raised when the user referenced by an HrEmployee's `user_id` does not exist."""


class ManagerNotFoundError(Exception):
    """Raised when the manager referenced by an HrEmployee does not exist."""


class SelfManagerError(Exception):
    """Raised when an HrEmployee's `manager_id` is set to its own id.

    Only a direct self-manager is rejected here -- recursive validation and
    cycle detection across the reporting line are explicitly out of scope.
    """


class DuplicateEmployeeNumberError(Exception):
    """Raised when an employee number is already in use."""


class DuplicateEmployeeEmailError(Exception):
    """Raised when an employee email is already in use."""


class HrEmployeeService:
    """Business logic for `HrEmployee`. Owns the transaction boundary via a UoW.

    An HrEmployee's department, position, and team must each belong to its
    organization; its team must additionally belong to its department. This
    mirrors `TeamService`'s and `PositionService`'s cross-column invariants,
    which aren't expressible as plain FKs. `manager_id` is only checked for
    existence and for direct self-reference -- no recursive validation, no
    cycle detection, no reporting-tree traversal.

    Returned entities are expunged from the unit-of-work's session before it
    closes: the UoW always rolls back (and thus expires all attributes) on
    exit, so callers holding on to the entity after this method returns would
    otherwise hit a `DetachedInstanceError` on first attribute access.

    `update` additionally refreshes the entity before expunging it: `updated_at`
    is a server-side `onupdate`, and SQLAlchemy does not eagerly fetch it back
    via RETURNING after a plain UPDATE flush the way it does for INSERT, so it
    would otherwise be left expired -- refreshing while still attached avoids a
    `MissingGreenlet` (the ORM's lazy-load-on-attribute-access is not awaitable
    once the session has exited its async context).
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: EmployeeCreate) -> HrEmployee:
        async with self._uow_factory() as uow:
            repo = HrEmployeeRepository(uow.session)

            if not await OrganizationRepository(uow.session).exists(data.organization_id):
                raise OrganizationNotFoundError(str(data.organization_id))

            department = await DepartmentRepository(uow.session).get(data.department_id)
            if department is None:
                raise DepartmentNotFoundError(str(data.department_id))
            if department.organization_id != data.organization_id:
                raise DepartmentOrganizationMismatchError(str(data.department_id))

            position = await PositionRepository(uow.session).get(data.position_id)
            if position is None:
                raise PositionNotFoundError(str(data.position_id))
            if position.organization_id != data.organization_id:
                raise PositionOrganizationMismatchError(str(data.position_id))

            team = await TeamRepository(uow.session).get(data.team_id)
            if team is None:
                raise TeamNotFoundError(str(data.team_id))
            if team.organization_id != data.organization_id:
                raise TeamOrganizationMismatchError(str(data.team_id))
            if team.department_id != data.department_id:
                raise TeamDepartmentMismatchError(str(data.team_id))

            if await LocationRepository(uow.session).get(data.location_id) is None:
                raise LocationNotFoundError(str(data.location_id))

            if not await JobGradeRepository(uow.session).exists(data.job_grade_id):
                raise JobGradeNotFoundError(str(data.job_grade_id))

            if not await EmploymentTypeRepository(uow.session).exists(data.employment_type_id):
                raise EmploymentTypeNotFoundError(str(data.employment_type_id))

            if not await EmploymentStatusRepository(uow.session).exists(
                data.employment_status_id
            ):
                raise EmploymentStatusNotFoundError(str(data.employment_status_id))

            if not await ShiftRepository(uow.session).exists(data.shift_id):
                raise ShiftNotFoundError(str(data.shift_id))

            if data.user_id is not None:
                if not await UserRepository(uow.session).exists(data.user_id):
                    raise UserNotFoundError(str(data.user_id))

            if data.manager_id is not None:
                if await repo.get(data.manager_id) is None:
                    raise ManagerNotFoundError(str(data.manager_id))

            if await repo.get_by_employee_number(data.employee_number):
                raise DuplicateEmployeeNumberError(data.employee_number)
            if await repo.get_by_email(data.email):
                raise DuplicateEmployeeEmailError(data.email)

            employee = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(employee)
            return employee

    async def get(self, employee_id: uuid.UUID) -> HrEmployee | None:
        async with self._uow_factory() as uow:
            repo = HrEmployeeRepository(uow.session)
            employee = await repo.get(employee_id)
            if employee is not None:
                uow.session.expunge(employee)
            return employee

    async def list(self) -> Sequence[HrEmployee]:
        async with self._uow_factory() as uow:
            repo = HrEmployeeRepository(uow.session)
            employees = await repo.list()
            uow.session.expunge_all()
            return employees

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[HrEmployee]:
        async with self._uow_factory() as uow:
            repo = HrEmployeeRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, employee_id: uuid.UUID, data: EmployeeUpdate) -> HrEmployee | None:
        """Updates an HrEmployee, including (as an administrative operation) its
        `organization_id`, `department_id`, `position_id`, `team_id`,
        `location_id`, and `manager_id`.

        The *effective* department, position, team, and manager (whichever
        values the employee will have once this update is applied -- whether
        part of this request or already set) are always validated against the
        *effective* organization (and, for team, the effective department too).
        This guarantees an employee can never end up pointing at references
        outside its own organization/department, even when an update only
        changes `organization_id` and leaves the others untouched.

        No cascading updates and no child updates: reassigning any of these
        references never touches other rows.
        """
        async with self._uow_factory() as uow:
            repo = HrEmployeeRepository(uow.session)
            employee = await repo.get(employee_id)
            if employee is None:
                return None

            values = data.model_dump(exclude_unset=True)

            organization_id = values.get("organization_id", employee.organization_id)
            department_id = values.get("department_id", employee.department_id)
            position_id = values.get("position_id", employee.position_id)
            team_id = values.get("team_id", employee.team_id)
            location_id = values.get("location_id", employee.location_id)
            manager_id = values.get("manager_id", employee.manager_id)
            job_grade_id = values.get("job_grade_id", employee.job_grade_id)
            employment_type_id = values.get("employment_type_id", employee.employment_type_id)
            employment_status_id = values.get(
                "employment_status_id", employee.employment_status_id
            )
            shift_id = values.get("shift_id", employee.shift_id)
            employee_number = values.get("employee_number", employee.employee_number)
            email = values.get("email", employee.email)

            if "organization_id" in values:
                if not await OrganizationRepository(uow.session).exists(organization_id):
                    raise OrganizationNotFoundError(str(organization_id))

            department = await DepartmentRepository(uow.session).get(department_id)
            if department is None:
                raise DepartmentNotFoundError(str(department_id))
            if department.organization_id != organization_id:
                raise DepartmentOrganizationMismatchError(str(department_id))

            position = await PositionRepository(uow.session).get(position_id)
            if position is None:
                raise PositionNotFoundError(str(position_id))
            if position.organization_id != organization_id:
                raise PositionOrganizationMismatchError(str(position_id))

            team = await TeamRepository(uow.session).get(team_id)
            if team is None:
                raise TeamNotFoundError(str(team_id))
            if team.organization_id != organization_id:
                raise TeamOrganizationMismatchError(str(team_id))
            if team.department_id != department_id:
                raise TeamDepartmentMismatchError(str(team_id))

            if await LocationRepository(uow.session).get(location_id) is None:
                raise LocationNotFoundError(str(location_id))

            if not await JobGradeRepository(uow.session).exists(job_grade_id):
                raise JobGradeNotFoundError(str(job_grade_id))

            if not await EmploymentTypeRepository(uow.session).exists(employment_type_id):
                raise EmploymentTypeNotFoundError(str(employment_type_id))

            if not await EmploymentStatusRepository(uow.session).exists(employment_status_id):
                raise EmploymentStatusNotFoundError(str(employment_status_id))

            if not await ShiftRepository(uow.session).exists(shift_id):
                raise ShiftNotFoundError(str(shift_id))

            if "user_id" in values and values["user_id"] is not None:
                if not await UserRepository(uow.session).exists(values["user_id"]):
                    raise UserNotFoundError(str(values["user_id"]))

            if manager_id == employee_id:
                raise SelfManagerError(str(employee_id))
            if manager_id is not None:
                if await repo.get(manager_id) is None:
                    raise ManagerNotFoundError(str(manager_id))

            if "employee_number" in values:
                existing = await repo.get_by_employee_number(employee_number)
                if existing is not None and existing.id != employee_id:
                    raise DuplicateEmployeeNumberError(employee_number)

            if "email" in values:
                existing = await repo.get_by_email(email)
                if existing is not None and existing.id != employee_id:
                    raise DuplicateEmployeeEmailError(email)

            updated = await repo.update(employee_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, employee_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = HrEmployeeRepository(uow.session)
            deleted = await repo.delete(employee_id)
            if deleted:
                await uow.commit()
            return deleted
