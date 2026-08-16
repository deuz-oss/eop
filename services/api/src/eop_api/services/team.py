import uuid
from collections.abc import Callable, Sequence

from eop_api.exceptions.department import DepartmentOrganizationMismatchError
from eop_api.models.team import Team
from eop_api.repositories.department import DepartmentRepository
from eop_api.repositories.organization import OrganizationRepository
from eop_api.repositories.team import TeamRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.schemas.team import TeamCreate, TeamUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class OrganizationNotFoundError(Exception):
    """Raised when the organization referenced by a Team does not exist.

    Local to the Team module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class DepartmentNotFoundError(Exception):
    """Raised when the department referenced by a Team does not exist."""


class ParentTeamNotFoundError(Exception):
    """Raised when the parent referenced by a Team does not exist."""


class ParentOrganizationMismatchError(Exception):
    """Raised when a Team's parent belongs to a different organization."""


class ParentDepartmentMismatchError(Exception):
    """Raised when a Team's parent belongs to a different department."""


class SelfParentTeamError(Exception):
    """Raised when a Team's `parent_id` is set to its own id."""


class CyclicParentTeamError(Exception):
    """Raised when a Team's proposed `parent_id` is already a descendant of
    the Team being updated -- a multi-hop cycle (e.g. A -> B -> A) rather
    than the single-node case `SelfParentTeamError` covers.
    """


class DuplicateTeamCodeError(Exception):
    """Raised when a team code is already used within its organization."""


class TeamService:
    """Business logic for `Team`. Owns the transaction boundary via a UoW.

    A Team's parent (when set) must belong to both the same Organization
    *and* the same Department as the Team itself -- a stricter invariant
    than Department's own parent, which only needs to share an Organization.

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

    async def create(self, data: TeamCreate) -> Team:
        async with self._uow_factory() as uow:
            repo = TeamRepository(uow.session)
            org_repo = OrganizationRepository(uow.session)
            dept_repo = DepartmentRepository(uow.session)

            if not await org_repo.exists(data.organization_id):
                raise OrganizationNotFoundError(str(data.organization_id))

            department = await dept_repo.get(data.department_id)
            if department is None:
                raise DepartmentNotFoundError(str(data.department_id))
            if department.organization_id != data.organization_id:
                raise DepartmentOrganizationMismatchError(str(data.department_id))

            if data.parent_id is not None:
                parent = await repo.get(data.parent_id)
                if parent is None:
                    raise ParentTeamNotFoundError(str(data.parent_id))
                if parent.organization_id != data.organization_id:
                    raise ParentOrganizationMismatchError(str(data.parent_id))
                if parent.department_id != data.department_id:
                    raise ParentDepartmentMismatchError(str(data.parent_id))

            if await repo.get_by_organization_and_code(data.organization_id, data.code):
                raise DuplicateTeamCodeError(data.code)

            team = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(team)
            return team

    async def get(self, team_id: uuid.UUID) -> Team | None:
        async with self._uow_factory() as uow:
            repo = TeamRepository(uow.session)
            team = await repo.get(team_id)
            if team is not None:
                uow.session.expunge(team)
            return team

    async def list(self) -> Sequence[Team]:
        async with self._uow_factory() as uow:
            repo = TeamRepository(uow.session)
            teams = await repo.list()
            uow.session.expunge_all()
            return teams

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Team]:
        async with self._uow_factory() as uow:
            repo = TeamRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, team_id: uuid.UUID, data: TeamUpdate) -> Team | None:
        """Updates a Team, including (as an administrative operation) its
        `organization_id` and `department_id`.

        The *effective* department and parent (whichever `department_id` /
        `parent_id` the team will have once this update is applied -- whether
        part of this request or already set) are always validated against the
        *effective* organization (and, for the parent, the effective
        department too). This guarantees a team can never end up pointing at a
        department or parent outside its own organization/department, even
        when an update only changes `organization_id` and leaves the others
        untouched.

        Reassigning `organization_id` or `department_id` never touches other
        rows: children keep their existing `organization_id`/`department_id`/
        `parent_id` and are not moved, cascaded, or otherwise recursively
        updated -- so moving a team can leave its *children* pointing at a now-
        mismatched organization or department. Callers who reassign a team are
        responsible for reconciling its children themselves.
        """
        async with self._uow_factory() as uow:
            repo = TeamRepository(uow.session)
            team = await repo.get(team_id)
            if team is None:
                return None

            values = data.model_dump(exclude_unset=True)

            organization_id = values.get("organization_id", team.organization_id)
            department_id = values.get("department_id", team.department_id)
            parent_id = values.get("parent_id", team.parent_id)
            code = values.get("code", team.code)

            if parent_id == team_id:
                raise SelfParentTeamError(str(team_id))

            if "organization_id" in values:
                org_repo = OrganizationRepository(uow.session)
                if not await org_repo.exists(organization_id):
                    raise OrganizationNotFoundError(str(organization_id))

            dept_repo = DepartmentRepository(uow.session)
            department = await dept_repo.get(department_id)
            if department is None:
                raise DepartmentNotFoundError(str(department_id))
            if department.organization_id != organization_id:
                raise DepartmentOrganizationMismatchError(str(department_id))

            if parent_id is not None:
                parent = await repo.get(parent_id)
                if parent is None:
                    raise ParentTeamNotFoundError(str(parent_id))
                if parent.organization_id != organization_id:
                    raise ParentOrganizationMismatchError(str(parent_id))
                if parent.department_id != department_id:
                    raise ParentDepartmentMismatchError(str(parent_id))
                if await self._would_create_cycle(repo, team_id, parent_id):
                    raise CyclicParentTeamError(str(parent_id))

            if "organization_id" in values or "code" in values:
                existing = await repo.get_by_organization_and_code(organization_id, code)
                if existing is not None and existing.id != team_id:
                    raise DuplicateTeamCodeError(code)

            updated = await repo.update(team_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, team_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = TeamRepository(uow.session)
            deleted = await repo.delete(team_id)
            if deleted:
                await uow.commit()
            return deleted

    @staticmethod
    async def _would_create_cycle(
        repo: TeamRepository, team_id: uuid.UUID, proposed_parent_id: uuid.UUID
    ) -> bool:
        """Whether assigning `proposed_parent_id` as `team_id`'s parent would
        create a multi-hop cycle -- i.e. whether `team_id` is already an
        ancestor of `proposed_parent_id`.

        Walks up from `proposed_parent_id` via `parent_id` one hop at a time.
        `visited` guards against looping forever should the tree already
        contain a cycle from data predating this check.
        """
        visited: set[uuid.UUID] = set()
        current_id: uuid.UUID | None = proposed_parent_id
        while current_id is not None:
            if current_id == team_id:
                return True
            if current_id in visited:
                return False
            visited.add(current_id)
            current = await repo.get(current_id)
            current_id = current.parent_id if current is not None else None
        return False
