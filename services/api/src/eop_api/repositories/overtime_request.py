import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.overtime_request import OvertimeRequest
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (OvertimeRequest.reason,)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": OvertimeRequest.employee_id,
    "status": OvertimeRequest.status,
    "overtime_date": OvertimeRequest.overtime_date,
}


class OvertimeRequestRepository(BaseRepository[OvertimeRequest]):
    """Data access layer for `OvertimeRequest`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OvertimeRequest)

    async def get_by_employee(self, employee_id: uuid.UUID) -> Sequence[OvertimeRequest]:
        stmt = select(OvertimeRequest).where(OvertimeRequest.employee_id == employee_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[OvertimeRequest]:
        """Paginated listing, text-searched against `reason`.

        Filterable by `employee_id`, `status`, and `overtime_date`.
        """
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
