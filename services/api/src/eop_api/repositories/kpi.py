from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.kpi import Kpi
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (Kpi.code, Kpi.name)


class KpiRepository(BaseRepository[Kpi]):
    """Data access layer for `Kpi`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Kpi)

    async def get_by_code(self, code: str) -> Kpi | None:
        stmt = select(Kpi).where(Kpi.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[Kpi]:
        """Paginated listing, text-searched against `code`/`name` by default."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields,
        )
