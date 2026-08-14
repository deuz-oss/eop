"""Provisions the initial administrator account.

This exists outside the Business API on purpose: role-gated endpoints have no
way to create the very first admin (creating a role and assigning it both
require the `admin` role already). Bootstrapping identity is an operational
concern, not something the API should special-case for.

Run from `services/api`:

    uv run python scripts/create_admin.py

Configure via environment variables (falls back to `.env`-loaded settings for
the database connection, same as the API):

    ADMIN_EMAIL       (default: admin@example.com)
    ADMIN_PASSWORD    (default: change-me -- development only, see below)
    ADMIN_FULL_NAME   (default: Administrator)

The insecure default password is only accepted when the app's own
`ENVIRONMENT` setting (`eop_api.core.config.settings.environment`) is
"development" -- the same setting the API itself uses. Anywhere else, a real
`ADMIN_PASSWORD` is required and the script refuses to run without one, so an
admin account with a known password can never be provisioned unnoticed.

Idempotent: safe to run any number of times. Each run creates only whatever
is missing (the `admin` role, the user, the assignment) and leaves existing
records untouched.
"""

import asyncio
import os
import sys

from eop_api.core.config import settings
from eop_api.core.security import hash_password
from eop_api.repositories.role import RoleRepository
from eop_api.repositories.user import UserRepository
from eop_api.uow.sqlalchemy import SQLAlchemyUnitOfWork

ADMIN_ROLE_NAME = "admin"
DEFAULT_EMAIL = "admin@example.com"
DEFAULT_PASSWORD = "change-me"
DEFAULT_FULL_NAME = "Administrator"
DEVELOPMENT_ENVIRONMENT = "development"


def resolve_password() -> str:
    """Resolves ADMIN_PASSWORD, failing fast outside development if it's
    missing or still the insecure default.

    Runs before any database work: a rejected password must never reach the
    point of creating an account.
    """
    password = os.environ.get("ADMIN_PASSWORD", DEFAULT_PASSWORD)

    if settings.environment == DEVELOPMENT_ENVIRONMENT:
        if password == DEFAULT_PASSWORD:
            print(
                "WARNING: ADMIN_PASSWORD not set, using the insecure development "
                "default. This is only allowed because ENVIRONMENT=development."
            )
        return password

    if password == DEFAULT_PASSWORD:
        print(
            f"ERROR: ADMIN_PASSWORD is missing or still set to the insecure "
            f"development default ('{DEFAULT_PASSWORD}'). Refusing to provision "
            f"an administrator while ENVIRONMENT={settings.environment!r}. "
            "Set ADMIN_PASSWORD to a real secret and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    return password


async def create_admin(password: str) -> None:
    email = os.environ.get("ADMIN_EMAIL", DEFAULT_EMAIL)
    full_name = os.environ.get("ADMIN_FULL_NAME", DEFAULT_FULL_NAME)

    async with SQLAlchemyUnitOfWork() as uow:
        user_repo = UserRepository(uow.session)
        role_repo = RoleRepository(uow.session)

        user = await user_repo.get_by_email(email)
        if user is None:
            user = await user_repo.create(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                is_active=True,
            )
            print(f"Created administrator user: {email}")
        else:
            print(f"Administrator user already exists: {email}")

        role = await role_repo.get_by_name(ADMIN_ROLE_NAME)
        if role is None:
            role = await role_repo.create(name=ADMIN_ROLE_NAME, description="Full system access")
            print(f"Created role: {ADMIN_ROLE_NAME}")
        else:
            print(f"Role already exists: {ADMIN_ROLE_NAME}")

        if await role_repo.is_assigned(role.id, user.id):
            print(f"Role '{ADMIN_ROLE_NAME}' already assigned to {email}")
        else:
            await role_repo.assign_user(role.id, user.id)
            print(f"Assigned role '{ADMIN_ROLE_NAME}' to {email}")

        await uow.commit()

    print("Administrator bootstrap complete.")


def main() -> None:
    password = resolve_password()
    asyncio.run(create_admin(password))


if __name__ == "__main__":
    main()
