import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.payroll_run import PayrollRunCreate, PayrollRunResponse, PayrollRunUpdate
from eop_api.schemas.payslip import PayslipResponse
from eop_api.services.payroll_calculation import PayrollCalculationService
from eop_api.services.payroll_run import (
    DuplicatePayrollRunCodeError,
    InvalidPayrollRunTransitionError,
    PayrollRunHasPayslipsError,
    PayrollRunService,
)
from eop_api.services.payslip import PayrollRunNotFoundError

router = APIRouter(prefix="/hr/payroll-runs", tags=["Payroll Runs"])


def get_payroll_run_service() -> PayrollRunService:
    return PayrollRunService()


PayrollRunServiceDep = Annotated[PayrollRunService, Depends(get_payroll_run_service)]


def get_payroll_calculation_service() -> PayrollCalculationService:
    return PayrollCalculationService()


PayrollCalculationServiceDep = Annotated[
    PayrollCalculationService, Depends(get_payroll_calculation_service)
]

# PayrollRun Authorization Policy: Role Based (`RequireRole("admin")`), not Owner
# Only -- `PayrollRun` carries no `employee_id` (`models/payroll_run.py`), so no
# resource field exists for an `AuthorizationEvaluator` to compare, per
# `docs/architecture/capabilities/payroll-authorization/decision.md` Addendum.
# Reuses the same `"admin"` role/mechanism `api/roles.py` already established
# as this repository's only precedent for privileged, non-owner-scoped access
# -- no new authorization framework introduced.
RequirePayrollAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=PayrollRunResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_run(
    data: PayrollRunCreate, service: PayrollRunServiceDep, _: RequirePayrollAdmin
) -> PayrollRunResponse:
    try:
        payroll_run = await service.create(data)
    except DuplicatePayrollRunCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payroll run code already exists",
        ) from exc
    return PayrollRunResponse.model_validate(payroll_run)


@router.get("", response_model=list[PayrollRunResponse])
async def list_payroll_runs(
    service: PayrollRunServiceDep, _: RequirePayrollAdmin
) -> list[PayrollRunResponse]:
    payroll_runs = await service.list()
    return [PayrollRunResponse.model_validate(payroll_run) for payroll_run in payroll_runs]


@router.get("/paginated", response_model=Page[PayrollRunResponse])
async def list_payroll_runs_paginated(
    service: PayrollRunServiceDep,
    pagination: Pagination,
    search: Search,
    _: RequirePayrollAdmin,
) -> Page[PayrollRunResponse]:
    page = await service.list_paginated(pagination, search)
    return Page(
        items=[PayrollRunResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{payroll_run_id}", response_model=PayrollRunResponse)
async def get_payroll_run(
    payroll_run_id: uuid.UUID, service: PayrollRunServiceDep, _: RequirePayrollAdmin
) -> PayrollRunResponse:
    payroll_run = await service.get(payroll_run_id)
    if payroll_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found")
    return PayrollRunResponse.model_validate(payroll_run)


@router.put("/{payroll_run_id}", response_model=PayrollRunResponse)
async def update_payroll_run(
    payroll_run_id: uuid.UUID,
    data: PayrollRunUpdate,
    service: PayrollRunServiceDep,
    _: RequirePayrollAdmin,
) -> PayrollRunResponse:
    try:
        payroll_run = await service.update(payroll_run_id, data)
    except DuplicatePayrollRunCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payroll run code already exists",
        ) from exc
    if payroll_run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found")
    return PayrollRunResponse.model_validate(payroll_run)


@router.delete("/{payroll_run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_payroll_run(
    payroll_run_id: uuid.UUID, service: PayrollRunServiceDep, _: RequirePayrollAdmin
) -> None:
    try:
        deleted = await service.delete(payroll_run_id)
    except PayrollRunHasPayslipsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payroll run has payslips and cannot be deleted",
        ) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found")


@router.post("/{payroll_run_id}/process", response_model=list[PayslipResponse])
async def process_payroll_run(
    payroll_run_id: uuid.UUID,
    service: PayrollCalculationServiceDep,
    _: RequirePayrollAdmin,
) -> list[PayslipResponse]:
    """Runs Payroll Calculation for every eligible employee in `payroll_run_id`'s batch.

    Transitions the run `DRAFT -> PROCESSING -> COMPLETED`
    (`PayrollCalculationService.calculate_batch`); rejects a run that is not
    currently `DRAFT` (already processed, or processing already in
    progress).
    """
    try:
        payslips = await service.calculate_batch(payroll_run_id)
    except PayrollRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found"
        ) from exc
    except InvalidPayrollRunTransitionError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return [PayslipResponse.model_validate(payslip) for payslip in payslips]
