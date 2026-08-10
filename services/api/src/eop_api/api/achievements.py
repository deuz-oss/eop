import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.auth import CurrentUser
from eop_api.dependencies.pagination import Pagination
from eop_api.dependencies.rbac import RequireRole
from eop_api.schemas.achievement import AchievementCreate, AchievementResponse, AchievementUpdate
from eop_api.schemas.pagination import Page
from eop_api.services.achievement import (
    AchievementService,
    DuplicateAchievementError,
    TargetNotFoundError,
)

router = APIRouter(prefix="/achievements", tags=["Performance Management"])


def get_achievement_service() -> AchievementService:
    return AchievementService()


AchievementServiceDep = Annotated[AchievementService, Depends(get_achievement_service)]

# Achievement Authorization Policy: Role Based (`RequireRole("admin")`) -- an
# Achievement is manually recorded by an administrator, mirroring exactly how
# an administrator manually assigns the Target goal
# (`docs/architecture/capabilities/performance/
# achievement-iteration-1-scope-and-implementation-plan.md` §8). No Owner
# Only evaluator exists for this entity. Reuses the same "admin" role/
# mechanism as `Kpi`/`Target`/`Store`, no new authorization framework
# introduced.
RequireAchievementAdmin = Annotated[CurrentUser, Depends(RequireRole("admin"))]


@router.post("", response_model=AchievementResponse, status_code=status.HTTP_201_CREATED)
async def create_achievement(
    data: AchievementCreate, service: AchievementServiceDep, _: RequireAchievementAdmin
) -> AchievementResponse:
    try:
        achievement = await service.create(data)
    except TargetNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Target not found"
        ) from exc
    except DuplicateAchievementError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An achievement already exists for this target",
        ) from exc
    return AchievementResponse.model_validate(achievement)


@router.get("", response_model=list[AchievementResponse])
async def list_achievements(
    service: AchievementServiceDep, _: RequireAchievementAdmin
) -> list[AchievementResponse]:
    achievements = await service.list()
    return [AchievementResponse.model_validate(item) for item in achievements]


@router.get("/paginated", response_model=Page[AchievementResponse])
async def list_achievements_paginated(
    service: AchievementServiceDep, pagination: Pagination, _: RequireAchievementAdmin
) -> Page[AchievementResponse]:
    page = await service.list_paginated(pagination)
    return Page(
        items=[AchievementResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(
    achievement_id: uuid.UUID, service: AchievementServiceDep, _: RequireAchievementAdmin
) -> AchievementResponse:
    achievement = await service.get(achievement_id)
    if achievement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")
    return AchievementResponse.model_validate(achievement)


@router.put("/{achievement_id}", response_model=AchievementResponse)
async def update_achievement(
    achievement_id: uuid.UUID,
    data: AchievementUpdate,
    service: AchievementServiceDep,
    _: RequireAchievementAdmin,
) -> AchievementResponse:
    achievement = await service.update(achievement_id, data)
    if achievement is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")
    return AchievementResponse.model_validate(achievement)


@router.delete("/{achievement_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_achievement(
    achievement_id: uuid.UUID, service: AchievementServiceDep, _: RequireAchievementAdmin
) -> None:
    deleted = await service.delete(achievement_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Achievement not found")
