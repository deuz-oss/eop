from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.audit_log import AuditLog
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (AuditLog.entity_type, AuditLog.action)


class AuditLogRepository(BaseRepository[AuditLog]):
    """Data access layer for `AuditLog`. Append-only: callers only create, get, and paginate."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AuditLog)

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[AuditLog]:
        """Paginated listing, text-searched against `entity_type`/`action` by default."""
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields,
        )
