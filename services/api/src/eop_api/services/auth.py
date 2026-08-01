import uuid
from collections.abc import Callable

from jwt import PyJWTError

from eop_api.core.security import create_access_token, decode_access_token, verify_password
from eop_api.models.user import User
from eop_api.repositories.user import UserRepository
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork


class InvalidCredentialsError(Exception):
    """Raised when the email is unknown or the password is incorrect.

    Both cases collapse into a single exception so the API layer cannot be
    used to enumerate registered emails.
    """


class InactiveUserError(Exception):
    """Raised when credentials are valid but the user account is inactive."""


class InvalidTokenError(Exception):
    """Raised when a bearer token is malformed, expired, or no longer resolves
    to an active user."""


class AuthService:
    """Business logic for authentication. Owns the transaction boundary via a UoW."""

    def __init__(
        self, uow_factory: Callable[[], SQLAlchemyUnitOfWork] = SQLAlchemyUnitOfWork
    ) -> None:
        self._uow_factory = uow_factory

    async def authenticate(self, email: str, password: str) -> User:
        async with self._uow_factory() as uow:
            repo = UserRepository(uow.session)
            user = await repo.get_by_email(email)
            if user is None or not verify_password(password, user.password_hash):
                raise InvalidCredentialsError(email)
            if not user.is_active:
                raise InactiveUserError(email)

            uow.session.expunge(user)
            return user

    async def login(self, email: str, password: str) -> str:
        user = await self.authenticate(email, password)
        return create_access_token(subject=str(user.id))

    async def get_current_user(self, token: str) -> User:
        try:
            payload = decode_access_token(token)
        except PyJWTError as exc:
            raise InvalidTokenError("Token is invalid or expired") from exc

        subject = payload.get("sub")
        if subject is None:
            raise InvalidTokenError("Token is missing a subject")

        try:
            user_id = uuid.UUID(subject)
        except ValueError as exc:
            raise InvalidTokenError("Token subject is not a valid user id") from exc

        async with self._uow_factory() as uow:
            repo = UserRepository(uow.session)
            user = await repo.get(user_id)
            if user is None or not user.is_active:
                raise InvalidTokenError("User not found or inactive")

            uow.session.expunge(user)
            return user
