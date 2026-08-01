import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from eop_api.services.project import (
    DuplicateProjectCodeError,
    OrganizationNotFoundError,
    ProjectService,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


def get_project_service() -> ProjectService:
    return ProjectService()


ProjectServiceDep = Annotated[ProjectService, Depends(get_project_service)]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(data: ProjectCreate, service: ProjectServiceDep) -> ProjectResponse:
    try:
        project = await service.create(data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DuplicateProjectCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project code already exists in this organization",
        ) from exc
    return ProjectResponse.model_validate(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(service: ProjectServiceDep) -> list[ProjectResponse]:
    projects = await service.list()
    return [ProjectResponse.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: uuid.UUID, service: ProjectServiceDep) -> ProjectResponse:
    project = await service.get(project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID, data: ProjectUpdate, service: ProjectServiceDep
) -> ProjectResponse:
    try:
        project = await service.update(project_id, data)
    except OrganizationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found"
        ) from exc
    except DuplicateProjectCodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project code already exists in this organization",
        ) from exc
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return ProjectResponse.model_validate(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: uuid.UUID, service: ProjectServiceDep) -> None:
    deleted = await service.delete(project_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
