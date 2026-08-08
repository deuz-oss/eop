from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.deduction_type import DeductionType
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (
    DeductionType.code,
    DeductionType.name,
)


class DeductionTypeRepository(BaseRepository[DeductionType]):
    """Data access layer for `DeductionType`. Never commits or rolls back.

    Mirrors `EmploymentTypeRepository` exactly.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, DeductionType)

    async def get_by_code(self, code: str) -> DeductionType | None:
        stmt = select(DeductionType).where(DeductionType.code == code)
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
    ) -> Page[DeductionType]:
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields,
        )
