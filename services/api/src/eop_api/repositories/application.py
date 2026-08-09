import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.application import Application
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "candidate_id": Application.candidate_id,
    "job_requisition_id": Application.job_requisition_id,
    "status": Application.status,
}


class ApplicationRepository(BaseRepository[Application]):
    """Data access layer for `Application`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Application)

    async def get_by_candidate_and_requisition(
        self, candidate_id: uuid.UUID, job_requisition_id: uuid.UUID
    ) -> Application | None:
        stmt = select(Application).where(
            Application.candidate_id == candidate_id,
            Application.job_requisition_id == job_requisition_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = (),
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[Application]:
        """Paginated listing, filterable by `candidate_id`/`job_requisition_id`/`status`."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
