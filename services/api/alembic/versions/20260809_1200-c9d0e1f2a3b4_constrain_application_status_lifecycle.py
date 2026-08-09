"""constrain application status to lifecycle enum

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-09 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: str | Sequence[str] | None = "b8c9d0e1f2a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_APPLICATION_STATUS_VALUES = (
    "applied",
    "screening",
    "interviewing",
    "offered",
    "hired",
    "rejected",
    "withdrawn",
)


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "applications",
        "status",
        existing_type=sa.String(length=50),
        type_=sa.Enum(
            *_APPLICATION_STATUS_VALUES,
            name="application_status",
            native_enum=False,
            length=20,
        ),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "applications",
        "status",
        existing_type=sa.Enum(
            *_APPLICATION_STATUS_VALUES,
            name="application_status",
            native_enum=False,
            length=20,
        ),
        type_=sa.String(length=50),
        existing_nullable=False,
    )
