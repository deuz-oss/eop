import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.department import Department
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (Department.name, Department.code)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "organization_id": Department.organization_id,
    "parent_id": Department.parent_id,
}


class DepartmentRepository(BaseRepository[Department]):
    """Data access layer for `Department`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Department)

    async def get_by_organization_and_code(
        self, organization_id: uuid.UUID, code: str
    ) -> Department | None:
        stmt = select(Department).where(
            Department.organization_id == organization_id,
            Department.code == code,
        )
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
    ) -> Page[Department]:
        """Paginated listing, text-searched against `name`/`code`.

        Filterable by `organization_id` and `parent_id`.
        """
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
