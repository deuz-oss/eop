import uuid
from collections.abc import Callable, Sequence

from eop_api.models.task import Task
from eop_api.repositories.employee import EmployeeRepository
from eop_api.repositories.project import ProjectRepository
from eop_api.repositories.task import TaskRepository
from eop_api.schemas.task import TaskCreate, TaskUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class ProjectNotFoundError(Exception):
    """Raised when the project referenced by a Task does not exist.

    Local to the Task module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class EmployeeNotFoundError(Exception):
    """Raised when the assignee referenced by a Task does not exist."""


class OrganizationMismatchError(Exception):
    """Raised when a Task's assignee and project belong to different organizations."""


class TaskService:
    """Business logic for `Task`. Owns the transaction boundary via a UoW.

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

    async def create(self, data: TaskCreate) -> Task:
        async with self._uow_factory() as uow:
            project_repo = ProjectRepository(uow.session)
            project = await project_repo.get(data.project_id)
            if project is None:
                raise ProjectNotFoundError(str(data.project_id))

            if data.assignee_id is not None:
                employee_repo = EmployeeRepository(uow.session)
                employee = await employee_repo.get(data.assignee_id)
                if employee is None:
                    raise EmployeeNotFoundError(str(data.assignee_id))

                if employee.organization_id != project.organization_id:
                    raise OrganizationMismatchError(
                        f"assignee {data.assignee_id} and project {data.project_id} "
                        "belong to different organizations"
                    )

            repo = TaskRepository(uow.session)
            task = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(task)
            return task

    async def get(self, task_id: uuid.UUID) -> Task | None:
        async with self._uow_factory() as uow:
            repo = TaskRepository(uow.session)
            task = await repo.get(task_id)
            if task is not None:
                uow.session.expunge(task)
            return task

    async def list(self) -> Sequence[Task]:
        async with self._uow_factory() as uow:
            repo = TaskRepository(uow.session)
            tasks = await repo.list()
            uow.session.expunge_all()
            return tasks

    async def update(self, task_id: uuid.UUID, data: TaskUpdate) -> Task | None:
        async with self._uow_factory() as uow:
            repo = TaskRepository(uow.session)
            task = await repo.get(task_id)
            if task is None:
                return None

            values = data.model_dump(exclude_unset=True)

            project_id = values.get("project_id", task.project_id)
            assignee_id = values.get("assignee_id", task.assignee_id)

            if "project_id" in values or "assignee_id" in values:
                project_repo = ProjectRepository(uow.session)
                project = await project_repo.get(project_id)
                if project is None:
                    raise ProjectNotFoundError(str(project_id))

                if assignee_id is not None:
                    employee_repo = EmployeeRepository(uow.session)
                    employee = await employee_repo.get(assignee_id)
                    if employee is None:
                        raise EmployeeNotFoundError(str(assignee_id))

                    if employee.organization_id != project.organization_id:
                        raise OrganizationMismatchError(
                            f"assignee {assignee_id} and project {project_id} "
                            "belong to different organizations"
                        )

            updated = await repo.update(task_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, task_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = TaskRepository(uow.session)
            deleted = await repo.delete(task_id)
            if deleted:
                await uow.commit()
            return deleted
