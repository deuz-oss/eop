import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.schemas.assignment import AssignmentCreate, AssignmentResponse, AssignmentUpdate
from eop_api.services.assignment import (
    AssignmentService,
    DuplicateAssignmentError,
    EmployeeNotFoundError,
    OrganizationMismatchError,
    ProjectNotFoundError,
)

router = APIRouter(prefix="/assignments", tags=["Assignments"])


def get_assignment_service() -> AssignmentService:
    return AssignmentService()


AssignmentServiceDep = Annotated[AssignmentService, Depends(get_assignment_service)]


@router.post("", response_model=AssignmentResponse, status_code=status.HTTP_201_CREATED)
async def create_assignment(
    data: AssignmentCreate, service: AssignmentServiceDep
) -> AssignmentResponse:
    try:
        assignment = await service.create(data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        ) from exc
    except OrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee and project belong to different organizations",
        ) from exc
    except DuplicateAssignmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment already exists for this employee and project",
        ) from exc
    return AssignmentResponse.model_validate(assignment)


@router.get("", response_model=list[AssignmentResponse])
async def list_assignments(service: AssignmentServiceDep) -> list[AssignmentResponse]:
    assignments = await service.list()
    return [AssignmentResponse.model_validate(assignment) for assignment in assignments]


@router.get("/{assignment_id}", response_model=AssignmentResponse)
async def get_assignment(
    assignment_id: uuid.UUID, service: AssignmentServiceDep
) -> AssignmentResponse:
    assignment = await service.get(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return AssignmentResponse.model_validate(assignment)


@router.patch("/{assignment_id}", response_model=AssignmentResponse)
async def update_assignment(
    assignment_id: uuid.UUID, data: AssignmentUpdate, service: AssignmentServiceDep
) -> AssignmentResponse:
    try:
        assignment = await service.update(assignment_id, data)
    except EmployeeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found"
        ) from exc
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        ) from exc
    except OrganizationMismatchError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee and project belong to different organizations",
        ) from exc
    except DuplicateAssignmentError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment already exists for this employee and project",
        ) from exc
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    return AssignmentResponse.model_validate(assignment)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assignment_id: uuid.UUID, service: AssignmentServiceDep) -> None:
    deleted = await service.delete(assignment_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
