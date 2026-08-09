from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.job_requisition import JobRequisition
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (
    JobRequisition.code,
    JobRequisition.title,
)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "organization_id": JobRequisition.organization_id,
    "department_id": JobRequisition.department_id,
    "position_id": JobRequisition.position_id,
    "status": JobRequisition.status,
}


class JobRequisitionRepository(BaseRepository[JobRequisition]):
    """Data access layer for `JobRequisition`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, JobRequisition)

    async def get_by_code(self, code: str) -> JobRequisition | None:
        return await self.get_by(JobRequisition.code, code)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[JobRequisition]:
        """Paginated listing, text-searched against `code`/`title`, filterable
        by `organization_id`/`department_id`/`position_id`/`status`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
