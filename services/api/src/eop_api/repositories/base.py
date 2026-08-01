import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from eop_api.db.base import BaseEntity
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams, SearchParams


class BaseRepository[ModelT: BaseEntity]:
    """Generic, model-agnostic data access layer over an AsyncSession.

    Subclass or instantiate directly with a concrete model to get typed
    CRUD access. Never commits: callers own the transaction boundary.
    """

    def __init__(self, session: AsyncSession, model: type[ModelT]) -> None:
        self.session = session
        self.model = model

    async def get(self, id: uuid.UUID) -> ModelT | None:
        return await self.session.get(self.model, id)

    async def list(self) -> Sequence[ModelT]:
        result = await self.session.execute(select(self.model))
        return result.scalars().all()

    async def create(self, **values: Any) -> ModelT:
        instance = self.model(**values)
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(self, id: uuid.UUID, **values: Any) -> ModelT | None:
        instance = await self.get(id)
        if instance is None:
            return None

        for field, value in values.items():
            setattr(instance, field, value)

        await self.session.flush()
        return instance

    async def delete(self, id: uuid.UUID) -> bool:
        instance = await self.get(id)
        if instance is None:
            return False

        await self.session.delete(instance)
        await self.session.flush()
        return True

    async def exists(self, id: uuid.UUID) -> bool:
        stmt = select(self.model.id).where(self.model.id == id).limit(1)
        result = await self.session.execute(stmt)
        return result.first() is not None

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    def _apply_search(
        self,
        stmt: Select[Any],
        search: SearchParams | None,
        search_fields: Sequence[InstrumentedAttribute[Any]],
    ) -> Select[Any]:
        """Apply a case-insensitive partial-match filter across `search_fields`.

        No-ops if there is no search, no searchable fields were configured,
        or the search text is empty/whitespace-only.
        """
        if search is None or not search_fields:
            return stmt

        text = search.text
        if text is None:
            return stmt

        pattern = f"%{text}%"
        conditions = [column.ilike(pattern) for column in search_fields]
        return stmt.where(or_(*conditions))

    def _apply_filters(
        self,
        stmt: Select[Any],
        filters: FilterParams | None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]],
    ) -> Select[Any]:
        """Apply equality filters, restricted to the given allowlist.

        Only keys present in `filterable_fields` are applied; this is what
        prevents a client-supplied field name from ever reaching a raw SQL
        column. Keys outside the allowlist are silently ignored rather than
        raising, so this foundation never surfaces as an unhandled error --
        callers that want to reject unknown filter names should validate
        them at the API layer, before building a `FilterParams`.
        """
        if not filters:
            return stmt

        for field_name, value in filters.values.items():
            column = filterable_fields.get(field_name)
            if column is None:
                continue
            stmt = stmt.where(column == value)

        return stmt

    async def paginate(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        search: SearchParams | None = None,
        search_fields: Sequence[InstrumentedAttribute[Any]] = (),
        filters: FilterParams | None = None,
        filterable_fields: Mapping[str, InstrumentedAttribute[Any]] | None = None,
    ) -> Page[ModelT]:
        base_stmt = select(self.model)
        base_stmt = self._apply_search(base_stmt, search, search_fields)
        base_stmt = self._apply_filters(base_stmt, filters, filterable_fields or {})

        items_stmt = base_stmt.offset(offset).limit(limit)
        items_result = await self.session.execute(items_stmt)
        items = list(items_result.scalars().all())

        count_stmt = select(func.count()).select_from(self.model)
        count_stmt = self._apply_search(count_stmt, search, search_fields)
        count_stmt = self._apply_filters(count_stmt, filters, filterable_fields or {})
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar_one()

        return Page(items=items, total=total, offset=offset, limit=limit)
