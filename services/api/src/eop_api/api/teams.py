import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.search import Search
from eop_api.exceptions.department import DepartmentOrganizationMismatchError
from eop_api.schemas.pagination import Page
from eop_api.schemas.search import FilterParams
from eop_api.schemas.team import TeamCreate, TeamResponse, TeamUpdate
from eop_api.services.team import (
    CyclicParentTeamError,
    DepartmentNotFoundError,
    DuplicateTeamCodeError,
    OrganizationNotFoundError,
    ParentDepartmentMismatchError,
    ParentOrganizationMismatchError,
    ParentTeamNotFoundError,
    SelfParentTeamError,
    TeamService,
)

router = APIRouter(prefix="/teams", tags=["Teams"])


def get_team_service() -> TeamService:
    return TeamService()


TeamServiceDep = Annotated[TeamService, Depends(get_team_service)]


def get_team_filters(
    organization_id: Annotated[uuid.UUID | None, Query()] = None,
    department_id: Annotated[uuid.UUID | None, Query()] = None,
    parent_id: Annotated[uuid.UUID | None, Query()] = None,
) -> FilterParams:
    """Shared equality filters (`organization_id`, `department_id`, `parent_id`),
    scoped to Teams."""
    values: dict[str, Any] = {}
    if organization_id is not None:
        values["organization_id"] = organization_id
    if department_id is not None:
        values["department_id"] = department_id
    if parent_id is not None:
        values["parent_id"] = parent_id
    return FilterParams(values=values)


TeamFilters = Annotated[FilterParams, Depends(get_team_filters)]


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(data: TeamCreate, service: TeamServiceDep, _: CurrentUser) -> TeamResponse:
    try:
        team = await service.create(data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        ) from exc
    except DepartmentOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Department must belong to the same organization",
        ) from exc
    except ParentTeamNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parent team not found"
        ) from exc
    except ParentOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parent team must belong to the same organization",
        ) from exc
    except ParentDepartmentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parent team must belong to the same department",
        ) from exc
    except DuplicateTeamCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Team code already exists in this organization",
        ) from exc
    return TeamResponse.model_validate(team)


@router.get("", response_model=list[TeamResponse])
async def list_teams(service: TeamServiceDep, _: CurrentUser) -> list[TeamResponse]:
    teams = await service.list()
    return [TeamResponse.model_validate(team) for team in teams]


@router.get("/paginated", response_model=Page[TeamResponse])
async def list_teams_paginated(
    service: TeamServiceDep,
    pagination: Pagination,
    search: Search,
    filters: TeamFilters,
    _: CurrentUser,
) -> Page[TeamResponse]:
    page = await service.list_paginated(pagination, search, filters)
    return Page(
        items=[TeamResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(team_id: uuid.UUID, service: TeamServiceDep, _: CurrentUser) -> TeamResponse:
    team = await service.get(team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return TeamResponse.model_validate(team)


@router.put("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: uuid.UUID,
    data: TeamUpdate,
    service: TeamServiceDep,
    _: CurrentUser,
) -> TeamResponse:
    try:
        team = await service.update(team_id, data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DepartmentNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Department not found"
        ) from exc
    except DepartmentOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Department must belong to the same organization",
        ) from exc
    except SelfParentTeamError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A team cannot be its own parent",
        ) from exc
    except ParentTeamNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Parent team not found"
        ) from exc
    except ParentOrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parent team must belong to the same organization",
        ) from exc
    except ParentDepartmentMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Parent team must belong to the same department",
        ) from exc
    except CyclicParentTeamError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A team cannot be assigned a descendant as its parent",
        ) from exc
    except DuplicateTeamCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Team code already exists in this organization",
        ) from exc
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return TeamResponse.model_validate(team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(team_id: uuid.UUID, service: TeamServiceDep, _: CurrentUser) -> None:
    deleted = await service.delete(team_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
