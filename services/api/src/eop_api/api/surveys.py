import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from eop_api.dependencies.employee_context import CurrentRequestContext
from eop_api.dependencies.pagination import Pagination
from eop_api.schemas.pagination import Page
from eop_api.schemas.survey import SurveyCreate, SurveyResponse, SurveyUpdate
from eop_api.services.survey import (
    DuplicateSurveyError,
    SurveyAuthorizationDeniedError,
    SurveyService,
    VisitNotFoundError,
)

router = APIRouter(prefix="/surveys", tags=["Visit"])


def get_survey_service() -> SurveyService:
    return SurveyService()


SurveyServiceDep = Annotated[SurveyService, Depends(get_survey_service)]


@router.post("", response_model=SurveyResponse, status_code=status.HTTP_201_CREATED)
async def create_survey(
    data: SurveyCreate,
    service: SurveyServiceDep,
    request_context: CurrentRequestContext,
) -> SurveyResponse:
    try:
        survey = await service.create(data, request_context)
    except VisitNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found"
        ) from exc
    except DuplicateSurveyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="This visit already has a survey"
        ) from exc
    except SurveyAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return SurveyResponse.model_validate(survey)


@router.get("", response_model=list[SurveyResponse])
async def list_surveys(
    service: SurveyServiceDep, request_context: CurrentRequestContext
) -> list[SurveyResponse]:
    surveys = await service.list(request_context)
    return [SurveyResponse.model_validate(item) for item in surveys]


@router.get("/paginated", response_model=Page[SurveyResponse])
async def list_surveys_paginated(
    service: SurveyServiceDep,
    pagination: Pagination,
    request_context: CurrentRequestContext,
) -> Page[SurveyResponse]:
    page = await service.list_paginated(request_context, pagination)
    return Page(
        items=[SurveyResponse.model_validate(item) for item in page.items],
        total=page.total,
        offset=page.offset,
        limit=page.limit,
    )


@router.get("/by-visit/{visit_id}", response_model=SurveyResponse)
async def get_survey_by_visit(
    visit_id: uuid.UUID,
    service: SurveyServiceDep,
    request_context: CurrentRequestContext,
) -> SurveyResponse:
    try:
        survey = await service.get_by_visit_id(visit_id, request_context)
    except SurveyAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if survey is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")
    return SurveyResponse.model_validate(survey)


@router.get("/{survey_id}", response_model=SurveyResponse)
async def get_survey(
    survey_id: uuid.UUID,
    service: SurveyServiceDep,
    request_context: CurrentRequestContext,
) -> SurveyResponse:
    try:
        survey = await service.get(survey_id, request_context)
    except SurveyAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if survey is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")
    return SurveyResponse.model_validate(survey)


@router.put("/{survey_id}", response_model=SurveyResponse)
async def update_survey(
    survey_id: uuid.UUID,
    data: SurveyUpdate,
    service: SurveyServiceDep,
    request_context: CurrentRequestContext,
) -> SurveyResponse:
    try:
        survey = await service.update(survey_id, data, request_context)
    except SurveyAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if survey is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")
    return SurveyResponse.model_validate(survey)


@router.delete("/{survey_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_survey(
    survey_id: uuid.UUID,
    service: SurveyServiceDep,
    request_context: CurrentRequestContext,
) -> None:
    try:
        deleted = await service.delete(survey_id, request_context)
    except SurveyAuthorizationDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Survey not found")
