"""add approval fields to leave requests overtime requests and timesheets

Revision ID: f4a1c9e6b2d7
Revises: 0bf3c4001ca5
Create Date: 2026-08-03 19:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f4a1c9e6b2d7"
down_revision: str | Sequence[str] | None = "0bf3c4001ca5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("leave_requests", "overtime_requests", "timesheets")


def upgrade() -> None:
    """Upgrade schema."""
    for table in _TABLES:
        op.add_column(table, sa.Column("approved_by", sa.Uuid(), nullable=True))
        op.add_column(table, sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        op.add_column(table, sa.Column("rejection_reason", sa.String(length=1000), nullable=True))
        op.create_foreign_key(
            f"fk_{table}_approved_by_users",
            table,
            "users",
            ["approved_by"],
            ["id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table in _TABLES:
        op.drop_constraint(f"fk_{table}_approved_by_users", table, type_="foreignkey")
        op.drop_column(table, "rejection_reason")
        op.drop_column(table, "approved_at")
        op.drop_column(table, "approved_by")
