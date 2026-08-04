import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.schemas.reconciliation import AttendanceReconciliationResponse
from eop_api.services.reconciliation import EmployeeNotFoundError, ReconciliationService

router = APIRouter(prefix="/hr/reconciliation", tags=["Attendance Reconciliation"])


def get_reconciliation_service() -> ReconciliationService:
    return ReconciliationService()


ReconciliationServiceDep = Annotated[ReconciliationService, Depends(get_reconciliation_service)]


@router.get("", response_model=AttendanceReconciliationResponse)
async def get_reconciliation(
    service: ReconciliationServiceDep,
    _: CurrentUser,
    employee_id: Annotated[uuid.UUID, Query()],
    date: Annotated[date, Query()],
) -> AttendanceReconciliationResponse:
    try:
        return await service.reconcile(employee_id, date)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
