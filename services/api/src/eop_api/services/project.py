import uuid
from collections.abc import Callable, Sequence

from eop_api.models.project import Project
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.project import ProjectRepository
from eop_api.schemas.project import ProjectCreate, ProjectUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class OrganizationNotFoundError(Exception):
    """Raised when the organization referenced by a Project does not exist.

    Local to the Project module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class DuplicateProjectCodeError(Exception):
    """Raised when a project code is already used within its organization."""


class ProjectService:
    """Business logic for `Project`. Owns the transaction boundary via a UoW.

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

    async def create(self, data: ProjectCreate) -> Project:
        async with self._uow_factory() as uow:
            org_repo = OrganizationRepository(uow.session)
            if not await org_repo.exists(data.organization_id):
                raise OrganizationNotFoundError(str(data.organization_id))

            repo = ProjectRepository(uow.session)
            if await repo.get_by_organization_and_code(data.organization_id, data.code):
                raise DuplicateProjectCodeError(data.code)

            project = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(project)
            return project

    async def get(self, project_id: uuid.UUID) -> Project | None:
        async with self._uow_factory() as uow:
            repo = ProjectRepository(uow.session)
            project = await repo.get(project_id)
            if project is not None:
                uow.session.expunge(project)
            return project

    async def list(self) -> Sequence[Project]:
        async with self._uow_factory() as uow:
            repo = ProjectRepository(uow.session)
            projects = await repo.list()
            uow.session.expunge_all()
            return projects

    async def update(self, project_id: uuid.UUID, data: ProjectUpdate) -> Project | None:
        async with self._uow_factory() as uow:
            repo = ProjectRepository(uow.session)
            project = await repo.get(project_id)
            if project is None:
                return None

            values = data.model_dump(exclude_unset=True)

            organization_id = values.get("organization_id", project.organization_id)
            code = values.get("code", project.code)
            if "organization_id" in values or "code" in values:
                if "organization_id" in values:
                    org_repo = OrganizationRepository(uow.session)
                    if not await org_repo.exists(organization_id):
                        raise OrganizationNotFoundError(str(organization_id))

                existing = await repo.get_by_organization_and_code(organization_id, code)
                if existing is not None and existing.id != project_id:
                    raise DuplicateProjectCodeError(code)

            updated = await repo.update(project_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, project_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = ProjectRepository(uow.session)
            deleted = await repo.delete(project_id)
            if deleted:
                await uow.commit()
            return deleted
