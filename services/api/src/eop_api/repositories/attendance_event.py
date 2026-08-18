import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.models.attendance_event import AttendanceEvent
from eop_api.repositories.base import BaseRepository
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams

SEARCHABLE_FIELDS: Sequence[InstrumentedAttribute[Any]] = (AttendanceEvent.remarks,)
FILTERABLE_FIELDS: Mapping[str, InstrumentedAttribute[Any]] = {
    "employee_id": AttendanceEvent.employee_id,
    "shift_id": AttendanceEvent.shift_id,
    "event_type": AttendanceEvent.event_type,
    "source": AttendanceEvent.source,
}


class AttendanceEventRepository(BaseRepository[AttendanceEvent]):
    """Data access layer for `AttendanceEvent`. Never commits or rolls back."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AttendanceEvent)

    async def exists_between(self, employee_id: uuid.UUID, start: datetime, end: datetime) -> bool:
        """Whether any `AttendanceEvent` falls within `[start, end]` for `employee_id`.

        Single-table, same-model query only -- no join against any other
        aggregate, and no interpretation of what the range means. `start`/
        `end` are opaque bounds supplied by the caller; this repository does
        not determine a UTC day, a local day, a timezone, a shift boundary,
        or any other calendar interpretation -- that belongs entirely to the
        orchestration layer (`ReconciliationService`), per
        `docs/architecture/ATTENDANCE_RECONCILIATION_DESIGN.md` §5/§12.4.

        Not called by `ReconciliationService` (AttendanceEvent Integrity
        workstream, correction lineage): a plain existence check cannot
        distinguish a superseded event from an authoritative one, so
        `reconcile()` uses `list_between`/`find_corrected_ids` instead. Kept
        here, unused but still tested, as a general-purpose primitive -- not
        removed, since no evidence requires removing a working, documented
        method beyond its one former caller no longer needing it.
        """
        stmt = (
            select(AttendanceEvent.id)
            .where(
                AttendanceEvent.employee_id == employee_id,
                AttendanceEvent.event_time >= start,
                AttendanceEvent.event_time <= end,
            )
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def list_between(
        self, employee_id: uuid.UUID, start: datetime, end: datetime
    ) -> Sequence[AttendanceEvent]:
        """Every `AttendanceEvent` within `[start, end]` for `employee_id`.

        Persistence-only: returns every raw match, unresolved -- mirrors
        `CompensationRepository.list_effective_as_of`'s exact precedent
        ("returns every raw match, unresolved... resolving that down to one
        answer is [the service]'s job, not this repository's"). Whether a
        returned row has since been superseded by a correction is not
        determined here; the caller (`ReconciliationService`) resolves that
        via `find_corrected_ids`.
        """
        stmt = select(AttendanceEvent).where(
            AttendanceEvent.employee_id == employee_id,
            AttendanceEvent.event_time >= start,
            AttendanceEvent.event_time <= end,
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def find_corrected_ids(self, event_ids: Sequence[uuid.UUID]) -> set[uuid.UUID]:
        """The subset of `event_ids` that are referenced as some *other*
        `AttendanceEvent`'s `corrects_id` -- i.e. have since been corrected.

        Purely structural (which ids have an incoming self-reference), not
        an interpretation of what that means -- mirrors `exists_between`'s
        own "no interpretation" boundary. Works for a correction chain of
        any depth: each corrected id in the chain is excluded independently,
        the same way `CompensationService._exclude_corrected_targets`
        excludes every corrected id from its own candidate set regardless
        of chain depth.
        """
        if not event_ids:
            return set()
        stmt = select(AttendanceEvent.corrects_id).where(AttendanceEvent.corrects_id.in_(event_ids))
        result = await self.session.execute(stmt)
        return {row for row in result.scalars().all() if row is not None}

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = SEARCHABLE_FIELDS,
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[AttendanceEvent]:
        """Paginated listing, text-searched against `remarks`.

        Filterable by `employee_id`, `shift_id`, `event_type`, and `source`.
        """
        return await super().paginate(
            offset=offset,
            limit=limit,
            search=search,
            search_fields=search_fields,
            filters=filters,
            filterable_fields=filterable_fields or FILTERABLE_FIELDS,
        )
