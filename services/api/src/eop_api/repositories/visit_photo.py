import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.visit import Visit
from eop_api.models.visit_photo import VisitPhoto
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "visit_id": VisitPhoto.visit_id,
}


class VisitPhotoRepository(BaseRepository[VisitPhoto]):
    """Data access layer for `VisitPhoto`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, VisitPhoto)

    async def paginate_by_employee_id(
        self,
        employee_id: uuid.UUID,
        *,
        offset: int = 0,
        limit: int = 50,
        visit_id: uuid.UUID | None = None,
    ) -> Page[VisitPhoto]:
        """VisitPhoto rows whose parent `Visit` belongs to `employee_id`,
        scoped at the SQL level via a join against `Visit`, optionally
        further filtered to one `visit_id`.

        Owner Only scoping cannot be expressed through the generic
        `FilterParams`/`filterable_fields` equality mechanism --
        `VisitPhoto` carries no `employee_id` of its own by design -- so
        this is a narrow, hand-written query specific to this repository,
        mirroring `PosmAuditRepository.paginate_by_employee_id`. The
        optional `visit_id` filter is layered onto the same join rather
        than routed through `FilterParams`, since the base query is
        already hand-written for the Owner Only scoping.
        """
        conditions = [Visit.employee_id == employee_id]
        if visit_id is not None:
            conditions.append(VisitPhoto.visit_id == visit_id)

        items_stmt = (
            select(VisitPhoto)
            .join(Visit, VisitPhoto.visit_id == Visit.id)
            .where(*conditions)
            .offset(offset)
            .limit(limit)
        )
        items_result = await self.session.execute(items_stmt)
        items = list(items_result.scalars().all())

        count_stmt = (
            select(func.count())
            .select_from(VisitPhoto)
            .join(Visit, VisitPhoto.visit_id == Visit.id)
            .where(*conditions)
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        return Page(items=items, total=total, offset=offset, limit=limit)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = (),
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[VisitPhoto]:
        """Paginated listing, filterable by `visit_id`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
