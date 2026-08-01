import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.schemas.task import TaskCreate, TaskResponse, TaskUpdate
from eop_api.services.task import (
    EmployeeNotFoundError,
    OrganizationMismatchError,
    ProjectNotFoundError,
    TaskService,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_task_service() -> TaskService:
    return TaskService()


TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(data: TaskCreate, service: TaskServiceDep) -> TaskResponse:
    try:
        task = await service.create(data)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        ) from exc
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except OrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignee and project belong to different organizations",
        ) from exc
    return TaskResponse.model_validate(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks(service: TaskServiceDep) -> list[TaskResponse]:
    tasks = await service.list()
    return [TaskResponse.model_validate(task) for task in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: uuid.UUID, service: TaskServiceDep) -> TaskResponse:
    task = await service.get(task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID, data: TaskUpdate, service: TaskServiceDep
) -> TaskResponse:
    try:
        task = await service.update(task_id, data)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        ) from exc
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except OrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignee and project belong to different organizations",
        ) from exc
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(task_id: uuid.UUID, service: TaskServiceDep) -> None:
    deleted = await service.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
