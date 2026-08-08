import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.schemas.deduction import DeductionResponse
from eop_api.services.deduction import DeductionAuthorizationDeniedError, DeductionService

router = APIRouter(prefix="/deductions", tags=["Deductions"])

# Read-only surface only: create/update/delete are deferred
# (`docs/architecture/capabilities/payroll-calculation/implementation-plan.md`
# §10.4) -- no admin/payroll-actor authorization concept exists anywhere in
# this codebase yet (`TECHNICAL_DEBT_REGISTER.md` TD-004). Deduction rows are
# entered internally/seeded directly until that exists. An employee viewing
# their own Deductions (Owner Only) does not require that concept.


def get_deduction_service() -> DeductionService:
    return DeductionService()


DeductionServiceDep = Annotated[DeductionService, Depends(get_deduction_service)]


@router.get("", response_model=list[DeductionResponse])
async def list_deductions(
    service: DeductionServiceDep, request_context: CurrentRequestContext
) -> list[DeductionResponse]:
    """Deduction records owned by the caller's own `employee_id`."""
    deductions = await service.list_by_employee(request_context)
    return [DeductionResponse.model_validate(item) for item in deductions]


@router.get("/{deduction_id}", response_model=DeductionResponse)
async def get_deduction(
    deduction_id: uuid.UUID,
    service: DeductionServiceDep,
    request_context: CurrentRequestContext,
) -> DeductionResponse:
    try:
        deduction = await service.get(deduction_id, request_context)
    except DeductionAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if deduction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deduction not found")
    return DeductionResponse.model_validate(deduction)
