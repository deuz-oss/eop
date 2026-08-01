from fastapi import APIRouter, HTTPException, status

from eop_api.dependencies.auth import AuthServiceDep, CurrentUser
from eop_api.schemas.auth import LoginRequest, TokenResponse
from eop_api.schemas.user import UserResponse
from eop_api.services.auth import InactiveUserError, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthServiceDep) -> TokenResponse:
    try:
        token = await service.login(data.email, data.password)
    except (InvalidCredentialsError, InactiveUserError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        ) from exc
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
