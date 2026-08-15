from fastapi import APIRouter, HTTPException, Request, status

from eop_api.core.logging import get_logger
from eop_api.core.login_throttle import account_key, client_ip_key, login_throttle
from eop_api.dependencies.auth import AuthServiceDep, CurrentUser
from eop_api.schemas.auth import LoginRequest, TokenResponse
from eop_api.schemas.user import UserResponse
from eop_api.services.auth import InactiveUserError, InvalidCredentialsError

router = APIRouter(prefix="/auth", tags=["Auth"])
logger = get_logger(__name__)


def _is_ip_throttled(*, account: str, ip: str) -> bool:
    """Read-only IP-scoped check. Fails open: an error here lets the login
    proceed as if the IP were not throttled rather than blocking a legitimate
    user. The IP dimension is checked -- and enforced -- independently of the
    account dimension: it must never be bypassable by supplying a correct
    password for an account that happens to also be over its own threshold."""
    try:
        return login_throttle.is_ip_throttled(ip)
    except Exception:
        logger.warning("login_throttle_check_failed", account=account, ip=ip)
        return False


def _is_account_throttled(*, account: str, ip: str) -> bool:
    """Read-only account-scoped check. Fails open: an error here lets the
    login proceed as if the account were not throttled."""
    try:
        return login_throttle.is_account_throttled(account)
    except Exception:
        logger.warning("login_throttle_check_failed", account=account, ip=ip)
        return False


def _record_login_failure(*, account: str, ip: str) -> float:
    """Fails open: an error here is logged and treated as no active delay
    rather than failing the request."""
    try:
        return login_throttle.record_failure(account_key=account, ip_key=ip)
    except Exception:
        logger.warning("login_throttle_record_failed", account=account, ip=ip)
        return 0.0


def _throttled_response(delay: float) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many login attempts. Please try again later.",
        headers={"Retry-After": str(int(delay))} if delay > 0 else None,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, service: AuthServiceDep, request: Request) -> TokenResponse:
    account = account_key(data.email)
    ip = client_ip_key(request)

    # IP-scoped throttling is authoritative and unconditional: it is checked
    # first, and a throttled IP is always rejected without ever evaluating
    # credentials -- a correct password must not be able to bypass it.
    if _is_ip_throttled(account=account, ip=ip):
        delay = _record_login_failure(account=account, ip=ip)
        raise _throttled_response(delay)

    # Account-scoped throttling, by contrast, must not block a *correct*
    # password: otherwise the legitimate owner could never reset their own
    # account's throttle state. Credentials are evaluated regardless of this
    # flag; it only decides which response a *failed* evaluation gets below.
    account_throttled = _is_account_throttled(account=account, ip=ip)

    try:
        token = await service.login(data.email, data.password)
    except (InvalidCredentialsError, InactiveUserError) as exc:
        delay = _record_login_failure(account=account, ip=ip)
        if account_throttled:
            raise _throttled_response(delay) from exc
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        ) from exc

    login_throttle.record_success(account_key=account)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
