import uuid
from collections.abc import Callable, Sequence

from eop_api.models.role import Role
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository
from eop_api.schemas.role import RoleCreate, RoleUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class RoleNotFoundError(Exception):
    """Raised when the role referenced by an operation does not exist.

    Local to the Role module: Foundation does not accumulate per-entity
    not-found exceptions, so this lives next to the only service that raises it.
    """


class UserNotFoundError(Exception):
    """Raised when the user referenced by a role assignment does not exist."""


class DuplicateRoleNameError(Exception):
    """Raised when a role name is already in use."""


class DuplicateRoleAssignmentError(Exception):
    """Raised when the user already holds the given role."""


class RoleService:
    """Business logic for `Role` and role assignment. Owns the transaction
    boundary via a UoW.

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

    async def create(self, data: RoleCreate) -> Role:
        async with self._uow_factory() as uow:
            repo = RoleRepository(uow.session)
            if await repo.get_by_name(data.name) is not None:
                raise DuplicateRoleNameError(data.name)

            role = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(role)
            return role

    async def get(self, role_id: uuid.UUID) -> Role | None:
        async with self._uow_factory() as uow:
            repo = RoleRepository(uow.session)
            role = await repo.get(role_id)
            if role is not None:
                uow.session.expunge(role)
            return role

    async def list(self) -> Sequence[Role]:
        async with self._uow_factory() as uow:
            repo = RoleRepository(uow.session)
            roles = await repo.list()
            uow.session.expunge_all()
            return roles

    async def update(self, role_id: uuid.UUID, data: RoleUpdate) -> Role | None:
        async with self._uow_factory() as uow:
            repo = RoleRepository(uow.session)
            role = await repo.get(role_id)
            if role is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "name" in values:
                existing = await repo.get_by_name(values["name"])
                if existing is not None and existing.id != role_id:
                    raise DuplicateRoleNameError(values["name"])

            updated = await repo.update(role_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, role_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = RoleRepository(uow.session)
            deleted = await repo.delete(role_id)
            if deleted:
                await uow.commit()
            return deleted

    async def assign_role(self, role_id: uuid.UUID, user_id: uuid.UUID) -> None:
        async with self._uow_factory() as uow:
            role_repo = RoleRepository(uow.session)
            if not await role_repo.exists(role_id):
                raise RoleNotFoundError(str(role_id))

            user_repo = UserRepository(uow.session)
            if not await user_repo.exists(user_id):
                raise UserNotFoundError(str(user_id))

            if await role_repo.is_assigned(role_id, user_id):
                raise DuplicateRoleAssignmentError(f"{role_id}:{user_id}")

            await role_repo.assign_user(role_id, user_id)
            await uow.commit()

    async def remove_role(self, role_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            role_repo = RoleRepository(uow.session)
            if not await role_repo.exists(role_id):
                raise RoleNotFoundError(str(role_id))

            user_repo = UserRepository(uow.session)
            if not await user_repo.exists(user_id):
                raise UserNotFoundError(str(user_id))

            removed = await role_repo.unassign_user(role_id, user_id)
            if removed:
                await uow.commit()
            return removed

    async def user_has_role(self, user_id: uuid.UUID, role_name: str) -> bool:
        async with self._uow_factory() as uow:
            repo = RoleRepository(uow.session)
            names = await repo.get_role_names_for_user(user_id)
            return role_name in names
