import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.schemas.pagination import Page
from eop_api.schemas.target import TargetCreate, TargetResponse, TargetUpdate
from eop_api.services.target import (
    DuplicateTargetError,
    EmployeeNotFoundError,
    KpiNotFoundError,
    TargetService,
)

router = APIRouter(prefix="/targets", tags=["Performance Management"])


def get_target_service() -> TargetService:
    return TargetService()


TargetServiceDep = Annotated[TargetService, Depends(get_target_service)]

# Target Authorization Policy: Role Based (`RequireRole("admin")`) -- a
# Target is assigned to an employee by an administrator, not self-authored
# by the employee (`docs/architecture/capabilities/performance/
# target-iteration-1-scope-and-implementation-plan.md` §8). `employee_id` is
# Target's business scope, not its authorization boundary -- no Owner Only
# evaluator exists for this entity. Reuses the same "admin" role/mechanism
# as `Kpi`/`Store`, no new authorization framework introduced.
RequireTargetAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(
    data: TargetCreate, service: TargetServiceDep, _: RequireTargetAdmin
) -> TargetResponse:
    try:
        target = await service.create(data)
    except KpiNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="KPI not found") from exc
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except DuplicateTargetError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A target already exists for this employee, KPI, and month",
        ) from exc
    return TargetResponse.model_validate(target)


@router.get("", response_model=list[TargetResponse])
async def list_targets(service: TargetServiceDep, _: RequireTargetAdmin) -> list[TargetResponse]:
    targets = await service.list()
    return [TargetResponse.model_validate(item) for item in targets]


@router.get("/paginated", response_model=Page[TargetResponse])
async def list_targets_paginated(
    service: TargetServiceDep, pagination: Pagination, _: RequireTargetAdmin
) -> Page[TargetResponse]:
    page = await service.list_paginated(pagination)
    return Page(
        items=[TargetResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: uuid.UUID, service: TargetServiceDep, _: RequireTargetAdmin
) -> TargetResponse:
    target = await service.get(target_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    return TargetResponse.model_validate(target)


@router.put("/{target_id}", response_model=TargetResponse)
async def update_target(
    target_id: uuid.UUID, data: TargetUpdate, service: TargetServiceDep, _: RequireTargetAdmin
) -> TargetResponse:
    target = await service.update(target_id, data)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
    return TargetResponse.model_validate(target)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(
    target_id: uuid.UUID, service: TargetServiceDep, _: RequireTargetAdmin
) -> None:
    deleted = await service.delete(target_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target not found")
