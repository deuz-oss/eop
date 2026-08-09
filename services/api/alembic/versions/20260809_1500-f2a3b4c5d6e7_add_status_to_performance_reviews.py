"""add status to performance reviews

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-09 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2a3b4c5d6e7"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "performance_reviews",
        sa.Column(
            "status",
            sa.Enum(
                "draft",
                "finalized",
                name="performance_review_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
            server_default="draft",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("performance_reviews", "status")
