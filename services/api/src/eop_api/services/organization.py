import uuid
from collections.abc import Callable, Sequence

from eop_api.models.organization import Organization
from eop_api.repositories.organization import OrganizationRepository
from eop_api.schemas.organization import OrganizationCreate, OrganizationUpdate
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class OrganizationService:
    """Business logic for `Organization`. Owns the transaction boundary via a UoW.

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

    async def create(self, data: OrganizationCreate) -> Organization:
        async with self._uow_factory() as uow:
            repo = OrganizationRepository(uow.session)
            organization = await repo.create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(organization)
            return organization

    async def get(self, organization_id: uuid.UUID) -> Organization | None:
        async with self._uow_factory() as uow:
            repo = OrganizationRepository(uow.session)
            organization = await repo.get(organization_id)
            if organization is not None:
                uow.session.expunge(organization)
            return organization

    async def list(self) -> Sequence[Organization]:
        async with self._uow_factory() as uow:
            repo = OrganizationRepository(uow.session)
            organizations = await repo.list()
            uow.session.expunge_all()
            return organizations

    async def update(
        self, organization_id: uuid.UUID, data: OrganizationUpdate
    ) -> Organization | None:
        async with self._uow_factory() as uow:
            repo = OrganizationRepository(uow.session)
            organization = await repo.update(organization_id, **data.model_dump(exclude_unset=True))
            if organization is None:
                return None
            await uow.commit()
            await uow.session.refresh(organization)
            uow.session.expunge(organization)
            return organization

    async def delete(self, organization_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = OrganizationRepository(uow.session)
            deleted = await repo.delete(organization_id)
            if deleted:
                await uow.commit()
            return deleted
