from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.foundation.monetary.types import InvalidMoneyError
from eop_api.schemas.payroll_calculation import PayrollCalculationRequest
from eop_api.schemas.payslip import PayslipResponse
from eop_api.services.payroll_calculation import (
    CompensationInactiveError,
    CompensationNotFoundError,
    DuplicatePayslipError,
    PayrollCalculationService,
)
from eop_api.services.payslip import EmployeeNotFoundError, PayrollRunNotFoundError

router = APIRouter(prefix="/payroll-calculation", tags=["Payroll Calculation"])


def get_payroll_calculation_service() -> PayrollCalculationService:
    return PayrollCalculationService()


PayrollCalculationServiceDep = Annotated[
    PayrollCalculationService, Depends(get_payroll_calculation_service)
]


@router.post("/calculate", response_model=PayslipResponse, status_code=status.HTTP_201_CREATED)
async def calculate_payroll(
    data: PayrollCalculationRequest, service: PayrollCalculationServiceDep, _: CurrentUser
) -> PayslipResponse:
    try:
        payslip = await service.calculate(data.payroll_run_id, data.employee_id)
    except CompensationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Compensation found for this employee",
        ) from exc
    except CompensationInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee's Compensation is not active",
        ) from exc
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except PayrollRunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Payroll run not found"
        ) from exc
    except DuplicatePayslipError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payslip already exists for this employee and payroll run",
        ) from exc
    except InvalidMoneyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return PayslipResponse.model_validate(payslip)
