import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.schemas.pagination import Page
from eop_api.schemas.payroll_run import PayrollRunCreate, PayrollRunResponse, PayrollRunUpdate
from eop_api.services.payroll_run import DuplicatePayrollRunCodeError, PayrollRunService

router = APIRouter(prefix="/hr/payroll-runs", tags=["Payroll Runs"])


def get_payroll_run_service() -> PayrollRunService:
    return PayrollRunService()


PayrollRunServiceDep = Annotated[PayrollRunService, Depends(get_payroll_run_service)]


@router.post("", response_model=PayrollRunResponse, status_code=status.HTTP_201_CREATED)
async def create_payroll_run(
    data: PayrollRunCreate, service: PayrollRunServiceDep, _: CurrentUser
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
    service: PayrollRunServiceDep, _: CurrentUser
) -> list[PayrollRunResponse]:
    payroll_runs = await service.list()
    return [PayrollRunResponse.model_validate(payroll_run) for payroll_run in payroll_runs]


@router.get("/paginated", response_model=Page[PayrollRunResponse])
async def list_payroll_runs_paginated(
    service: PayrollRunServiceDep,
    pagination: Pagination,
    search: Search,
    _: CurrentUser,
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
    payroll_run_id: uuid.UUID, service: PayrollRunServiceDep, _: CurrentUser
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
    _: CurrentUser,
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
    payroll_run_id: uuid.UUID, service: PayrollRunServiceDep, _: CurrentUser
) -> None:
    deleted = await service.delete(payroll_run_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found")
