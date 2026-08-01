import uuid
from collections.abc import Callable, Sequence

from eop_api.models.assignment import Assignment
from eop_api.repositories.assignment import AssignmentRepository
from eop_api.repositories.employee import EmployeeRepository
from eop_api.repositories.project import ProjectRepository
from eop_api.schemas.assignment import AssignmentCreate, AssignmentUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class EmployeeNotFoundError(Exception):
    """Raised when the employee referenced by an Assignment does not exist.

    Local to the Assignment module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class ProjectNotFoundError(Exception):
    """Raised when the project referenced by an Assignment does not exist."""


class OrganizationMismatchError(Exception):
    """Raised when the employee and project referenced by an Assignment belong
    to different organizations."""


class DuplicateAssignmentError(Exception):
    """Raised when an Assignment already exists for the given employee-project pair."""


class AssignmentService:
    """Business logic for `Assignment`. Owns the transaction boundary via a UoW.

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

    async def create(self, data: AssignmentCreate) -> Assignment:
        async with self._uow_factory() as uow:
            employee_repo = EmployeeRepository(uow.session)
            employee = await employee_repo.get(data.employee_id)
            if employee is None:
                raise EmployeeNotFoundError(str(data.employee_id))

            project_repo = ProjectRepository(uow.session)
            project = await project_repo.get(data.project_id)
            if project is None:
                raise ProjectNotFoundError(str(data.project_id))

            if employee.organization_id != project.organization_id:
                raise OrganizationMismatchError(
                    f"employee {data.employee_id} and project {data.project_id} "
                    "belong to different organizations"
                )

            repo = AssignmentRepository(uow.session)
            if await repo.get_by_employee_and_project(data.employee_id, data.project_id):
                raise DuplicateAssignmentError(f"{data.employee_id}:{data.project_id}")

            assignment = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(assignment)
            return assignment

    async def get(self, assignment_id: uuid.UUID) -> Assignment | None:
        async with self._uow_factory() as uow:
            repo = AssignmentRepository(uow.session)
            assignment = await repo.get(assignment_id)
            if assignment is not None:
                uow.session.expunge(assignment)
            return assignment

    async def list(self) -> Sequence[Assignment]:
        async with self._uow_factory() as uow:
            repo = AssignmentRepository(uow.session)
            assignments = await repo.list()
            uow.session.expunge_all()
            return assignments

    async def update(self, assignment_id: uuid.UUID, data: AssignmentUpdate) -> Assignment | None:
        async with self._uow_factory() as uow:
            repo = AssignmentRepository(uow.session)
            assignment = await repo.get(assignment_id)
            if assignment is None:
                return None

            values = data.model_dump(exclude_unset=True)

            employee_id = values.get("employee_id", assignment.employee_id)
            project_id = values.get("project_id", assignment.project_id)

            if "employee_id" in values or "project_id" in values:
                employee_repo = EmployeeRepository(uow.session)
                employee = await employee_repo.get(employee_id)
                if employee is None:
                    raise EmployeeNotFoundError(str(employee_id))

                project_repo = ProjectRepository(uow.session)
                project = await project_repo.get(project_id)
                if project is None:
                    raise ProjectNotFoundError(str(project_id))

                if employee.organization_id != project.organization_id:
                    raise OrganizationMismatchError(
                        f"employee {employee_id} and project {project_id} "
                        "belong to different organizations"
                    )

                existing = await repo.get_by_employee_and_project(employee_id, project_id)
                if existing is not None and existing.id != assignment_id:
                    raise DuplicateAssignmentError(f"{employee_id}:{project_id}")

            updated = await repo.update(assignment_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, assignment_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = AssignmentRepository(uow.session)
            deleted = await repo.delete(assignment_id)
            if deleted:
                await uow.commit()
            return deleted
