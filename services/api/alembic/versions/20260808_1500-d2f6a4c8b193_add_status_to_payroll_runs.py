"""add status to payroll runs

Revision ID: d2f6a4c8b193
Revises: e5a8c1f7d9b4
Create Date: 2026-08-08 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2f6a4c8b193"
down_revision: str | Sequence[str] | None = "e5a8c1f7d9b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "payroll_runs",
        sa.Column(
            "status",
            sa.Enum(
                "DRAFT",
                "PROCESSING",
                "COMPLETED",
                name="payroll_run_status",
                native_enum=False,
                length=20,
            ),
            nullable=False,
            server_default="DRAFT",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("payroll_runs", "status")
