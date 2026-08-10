import uuid
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.schemas.mission import MissionCreate, MissionResponse, MissionUpdate
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.services.mission import EmployeeNotFoundError, MissionService, StoreNotFoundError

router = APIRouter(prefix="/missions", tags=["Mission"])


def get_mission_service() -> MissionService:
    return MissionService()


MissionServiceDep = Annotated[MissionService, Depends(get_mission_service)]

# Authorization: Role Based (`RequireRole("admin")`) -- a Mission is a
# planning/assignment record created by an administrator ("Mission
# assignment" is an Area Manager action), not self-authored by the
# assigned employee (`docs/architecture/capabilities/mission/
# mission-iteration-1-scope-and-implementation-plan.md` §7/D7). No Owner
# Only evaluator exists for this entity. Reuses the same "admin" role/
# mechanism as `Kpi`/`Target`/`Achievement`, no new authorization
# framework introduced.
RequireMissionAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


def get_mission_filters(
    employee_id: Annotated[uuid.UUID | None, Query()] = None,
    store_id: Annotated[uuid.UUID | None, Query()] = None,
    scheduled_date: Annotated[date | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`employee_id`/`store_id`/`scheduled_date`),
    scoped to Missions."""
    values: dict[str, Any] = {}
    if employee_id is not None:
        values["employee_id"] = employee_id
    if store_id is not None:
        values["store_id"] = store_id
    if scheduled_date is not None:
        values["scheduled_date"] = scheduled_date
    return FilterParams(values=values)


MissionFilters = Annotated[FilterParams, Depends(get_mission_filters)]


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(
    data: MissionCreate, service: MissionServiceDep, _: RequireMissionAdmin
) -> MissionResponse:
    try:
        mission = await service.create(data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except StoreNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Store not found"
        ) from exc
    return MissionResponse.model_validate(mission)


@router.get("", response_model=list[MissionResponse])
async def list_missions(
    service: MissionServiceDep, _: RequireMissionAdmin
) -> list[MissionResponse]:
    missions = await service.list()
    return [MissionResponse.model_validate(item) for item in missions]


@router.get("/paginated", response_model=Page[MissionResponse])
async def list_missions_paginated(
    service: MissionServiceDep,
    pagination: Pagination,
    filters: MissionFilters,
    _: RequireMissionAdmin,
) -> Page[MissionResponse]:
    page = await service.list_paginated(pagination, filters)
    return Page(
        items=[MissionResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: uuid.UUID, service: MissionServiceDep, _: RequireMissionAdmin
) -> MissionResponse:
    mission = await service.get(mission_id)
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return MissionResponse.model_validate(mission)


@router.put("/{mission_id}", response_model=MissionResponse)
async def update_mission(
    mission_id: uuid.UUID,
    data: MissionUpdate,
    service: MissionServiceDep,
    _: RequireMissionAdmin,
) -> MissionResponse:
    try:
        mission = await service.update(mission_id, data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except StoreNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Store not found"
        ) from exc
    if mission is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return MissionResponse.model_validate(mission)


@router.delete("/{mission_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mission(
    mission_id: uuid.UUID, service: MissionServiceDep, _: RequireMissionAdmin
) -> None:
    deleted = await service.delete(mission_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found")
