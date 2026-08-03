import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from eop_api.models.leave_request import LeaveRequest
from eop_api.models.overtime_request import OvertimeRequest
from eop_api.models.timesheet import Timesheet
from eop_api.repositories.base import BaseRepository
from eop_api.repositories.leave_request import LeaveRequestRepository
from eop_api.repositories.overtime_request import OvertimeRequestRepository
from eop_api.repositories.timesheet import TimesheetRepository
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class ApprovalStatus(StrEnum):
    """The only two legal destinations for a `pending` request."""

    APPROVED = "approved"
    REJECTED = "rejected"


class InvalidApprovalStateError(Exception):
    """Raised when approve/reject is attempted on an entity that is not `pending`."""


class ApprovalService:
    """Orchestrates approve/reject decisions for `LeaveRequest`, `OvertimeRequest`,
    and `Timesheet`.

    This is the repository's first orchestration service (Option B, per
    `docs/architecture/APPROVAL_ORCHESTRATION_DESIGN.md`, adopted as an explicit
    architectural decision rather than inferred from repository evidence).
    Unlike every other service in this codebase, it does not own a single
    entity's CRUD -- it reaches into `LeaveRequestRepository`/
    `OvertimeRequestRepository`/`TimesheetRepository` directly, the same way
    every existing service already reaches into `HrEmployeeRepository`/
    `ShiftRepository` for a narrow, bounded purpose. It never calls another
    service, and `LeaveRequestService`/`OvertimeRequestService`/
    `TimesheetService` gain no `approve`/`reject` methods of their own.

    Only a `pending -> approved` / `pending -> rejected` transition is legal;
    anything else raises `InvalidApprovalStateError`. Authorization beyond
    authentication, decision history, audit logging, and event/notification
    dispatch are explicitly out of scope for this service.

    Returned entities are expunged from the unit-of-work's session before it
    closes (rollback-on-exit semantics), and refreshed before expunging --
    same `MissingGreenlet`/`onupdate` rationale documented on every other
    service in this codebase.
    """

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def approve_leave_request(
        self, leave_request_id: uuid.UUID, approver_id: uuid.UUID
    ) -> LeaveRequest | None:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            return await self._decide(
                uow,
                repo,
                leave_request_id,
                new_status=ApprovalStatus.APPROVED,
                approver_id=approver_id,
                rejection_reason=None,
            )

    async def reject_leave_request(
        self, leave_request_id: uuid.UUID, approver_id: uuid.UUID, reason: str
    ) -> LeaveRequest | None:
        async with self._uow_factory() as uow:
            repo = LeaveRequestRepository(uow.session)
            return await self._decide(
                uow,
                repo,
                leave_request_id,
                new_status=ApprovalStatus.REJECTED,
                approver_id=approver_id,
                rejection_reason=reason,
            )

    async def approve_overtime_request(
        self, overtime_request_id: uuid.UUID, approver_id: uuid.UUID
    ) -> OvertimeRequest | None:
        async with self._uow_factory() as uow:
            repo = OvertimeRequestRepository(uow.session)
            return await self._decide(
                uow,
                repo,
                overtime_request_id,
                new_status=ApprovalStatus.APPROVED,
                approver_id=approver_id,
                rejection_reason=None,
            )

    async def reject_overtime_request(
        self, overtime_request_id: uuid.UUID, approver_id: uuid.UUID, reason: str
    ) -> OvertimeRequest | None:
        async with self._uow_factory() as uow:
            repo = OvertimeRequestRepository(uow.session)
            return await self._decide(
                uow,
                repo,
                overtime_request_id,
                new_status=ApprovalStatus.REJECTED,
                approver_id=approver_id,
                rejection_reason=reason,
            )

    async def approve_timesheet(
        self, timesheet_id: uuid.UUID, approver_id: uuid.UUID
    ) -> Timesheet | None:
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)
            return await self._decide(
                uow,
                repo,
                timesheet_id,
                new_status=ApprovalStatus.APPROVED,
                approver_id=approver_id,
                rejection_reason=None,
            )

    async def reject_timesheet(
        self, timesheet_id: uuid.UUID, approver_id: uuid.UUID, reason: str
    ) -> Timesheet | None:
        async with self._uow_factory() as uow:
            repo = TimesheetRepository(uow.session)
            return await self._decide(
                uow,
                repo,
                timesheet_id,
                new_status=ApprovalStatus.REJECTED,
                approver_id=approver_id,
                rejection_reason=reason,
            )

    async def _decide(
        self,
        uow: SQLAlchemyUnitOfWork,
        repo: BaseRepository[Any],
        entity_id: uuid.UUID,
        *,
        new_status: ApprovalStatus,
        approver_id: uuid.UUID,
        rejection_reason: str | None,
    ) -> Any:
        """Shared `pending -> approved`/`pending -> rejected` transition.

        `repo` is untyped (`BaseRepository[Any]`) deliberately: this method is
        private, called only by the six public methods above, each of which
        restores the precise per-entity return type at its own boundary.
        """
        entity = await repo.get(entity_id)
        if entity is None:
            return None

        if entity.status != "pending":
            raise InvalidApprovalStateError(
                f"{type(entity).__name__} {entity_id} is '{entity.status}', not 'pending'"
            )

        updated = await repo.update(
            entity_id,
            status=new_status.value,
            approved_by=approver_id,
            approved_at=datetime.now(UTC),
            rejection_reason=rejection_reason,
        )
        assert updated is not None
        await uow.commit()
        await uow.session.refresh(updated)
        uow.session.expunge(updated)
        return updated
