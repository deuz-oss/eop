import uuid
from collections.abc import Callable, Sequence

from eop_api.models.offer import Offer
from eop_api.repositories.application import ApplicationRepository
from eop_api.repositories.offer import OfferRepository
from eop_api.schemas.offer import OfferCreate, OfferUpdate
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import FilterParams, SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class ApplicationNotFoundError(Exception):
    """Raised when the application referenced by an Offer does not exist."""


class OfferService:
    """Business logic for `Offer`. Owns the transaction boundary via a UoW.

    Deliberately minimal: a single existence check on `application_id`, no
    uniqueness constraint (multiple offers per `Application` are
    permitted), no acceptance/rejection/expiry lifecycle, no compensation
    terms -- `Application` owns the recruitment lifecycle (Iteration 2). No
    coupling to `ApplicationService.transition` exists here.

    Returned entities are expunged from the unit-of-work's session before it
    closes, mirroring every other service in this repository.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def create(self, data: OfferCreate) -> Offer:
        async with self._uow_factory() as uow:
            if not await ApplicationRepository(uow.session).exists(data.application_id):
                raise ApplicationNotFoundError(str(data.application_id))

            offer = await OfferRepository(uow.session).create(**data.model_dump())
            await uow.commit()
            uow.session.expunge(offer)
            return offer

    async def get(self, offer_id: uuid.UUID) -> Offer | None:
        async with self._uow_factory() as uow:
            offer = await OfferRepository(uow.session).get(offer_id)
            if offer is not None:
                uow.session.expunge(offer)
            return offer

    async def list(self) -> Sequence[Offer]:
        async with self._uow_factory() as uow:
            offers = await OfferRepository(uow.session).list()
            uow.session.expunge_all()
            return offers

    async def list_paginated(
        self,
        pagination: PaginationParams,
        search: SearchParams | None = None,
        filters: FilterParams | None = None,
    ) -> Page[Offer]:
        async with self._uow_factory() as uow:
            page = await OfferRepository(uow.session).paginate(
                offset=pagination.offset, limit=pagination.limit, search=search, filters=filters
            )
            uow.session.expunge_all()
            return page

    async def update(self, offer_id: uuid.UUID, data: OfferUpdate) -> Offer | None:
        async with self._uow_factory() as uow:
            repo = OfferRepository(uow.session)
            offer = await repo.get(offer_id)
            if offer is None:
                return None

            values = data.model_dump(exclude_unset=True)

            if "application_id" in values and not await ApplicationRepository(uow.session).exists(
                values["application_id"]
            ):
                raise ApplicationNotFoundError(str(values["application_id"]))

            updated = await repo.update(offer_id, **values)
            assert updated is not None
            await uow.commit()
            await uow.session.refresh(updated)
            uow.session.expunge(updated)
            return updated

    async def delete(self, offer_id: uuid.UUID) -> bool:
        async with self._uow_factory() as uow:
            repo = OfferRepository(uow.session)
            deleted = await repo.delete(offer_id)
            if deleted:
                await uow.commit()
            return deleted
