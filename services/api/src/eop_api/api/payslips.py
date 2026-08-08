import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.foundation.monetary.types import InvalidMoneyError
from eop_api.schemas.payslip import PayslipCreate, PayslipResponse
from eop_api.services.payslip import (
    EmployeeNotFoundError,
    PayrollRunNotFoundError,
    PayslipService,
)

router = APIRouter(prefix="/payslips", tags=["Payslips"])


def get_payslip_service() -> PayslipService:
    return PayslipService()


PayslipServiceDep = Annotated[PayslipService, Depends(get_payslip_service)]


@router.post("", response_model=PayslipResponse, status_code=status.HTTP_201_CREATED)
async def create_payslip(
    data: PayslipCreate, service: PayslipServiceDep, _: CurrentUser
) -> PayslipResponse:
    try:
        payslip = await service.create(data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except PayrollRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found"
        ) from exc
    except InvalidMoneyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return PayslipResponse.model_validate(payslip)


@router.get("", response_model=list[PayslipResponse])
async def list_payslips(service: PayslipServiceDep, _: CurrentUser) -> list[PayslipResponse]:
    payslips = await service.list()
    return [PayslipResponse.model_validate(payslip) for payslip in payslips]


@router.get("/{payslip_id}", response_model=PayslipResponse)
async def get_payslip(
    payslip_id: uuid.UUID, service: PayslipServiceDep, _: CurrentUser
) -> PayslipResponse:
    payslip = await service.get(payslip_id)
    if payslip is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payslip not found")
    return PayslipResponse.model_validate(payslip)
