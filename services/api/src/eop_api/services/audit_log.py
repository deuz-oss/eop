import uuid
from collections.abc import Callable
from typing import Any

from eop_api.core.audit import AuditAction, AuditEntityType
from eop_api.models.audit_log import AuditLog
from eop_api.repositories.audit_log import AuditLogRepository
from eop_api.schemas.pagination import Page, PaginationParams
from eop_api.schemas.search import SearchParams
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class AuditLogService:
    """Business logic for `AuditLog`. Owns the transaction boundary via a UoW.

    `record` is the reusable entry point future business modules call to append
    an audit entry, e.g.:

        await audit_log_service.record(
            user_id=current_user.id,
            action=AuditAction.CREATE,
            entity_type=AuditEntityType.ORGANIZATION,
            entity_id=organization.id,
            details={...},
        )

    Nothing in this PR calls it yet -- it is infrastructure for later adoption.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def record(
        self,
        *,
        user_id: uuid.UUID | None,
        action: AuditAction,
        entity_type: AuditEntityType,
        entity_id: uuid.UUID,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        async with self._uow_factory() as uow:
            repo = AuditLogRepository(uow.session)
            audit_log = await repo.create(
                user_id=user_id,
                action=action.value,
                entity_type=entity_type.value,
                entity_id=entity_id,
                details=details,
            )
            await uow.commit()
            uow.session.expunge(audit_log)
            return audit_log

    async def list_paginated(
        self, pagination: PaginationParams, search: SearchParams | None = None
    ) -> Page[AuditLog]:
        async with self._uow_factory() as uow:
            repo = AuditLogRepository(uow.session)
            page = await repo.paginate(
                offset=pagination.offset, limit=pagination.limit, search=search
            )
            uow.session.expunge_all()
            return page
