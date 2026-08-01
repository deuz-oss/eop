import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from eop_api.db.base import BaseEntity
from eop_api.schemas.pagination import Page


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

    async def paginate(self, *, offset: int = 0, limit: int = 20) -> Page[ModelT]:
        items_stmt = select(self.model).offset(offset).limit(limit)
        items_result = await self.session.execute(items_stmt)
        items = list(items_result.scalars().all())

        total = await self.count()

        return Page(items=items, total=total, offset=offset, limit=limit)
