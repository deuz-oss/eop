"""add shift id to hr employees

Revision ID: e7a8ed87ea45
Revises: c4a9d3e17f56
Create Date: 2026-08-03 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7a8ed87ea45"
down_revision: str | Sequence[str] | None = "c4a9d3e17f56"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("hr_employees", sa.Column("shift_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_hr_employees_shift_id_shifts",
        "hr_employees",
        "shifts",
        ["shift_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_hr_employees_shift_id",
        "hr_employees",
        ["shift_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_hr_employees_shift_id", table_name="hr_employees")
    op.drop_constraint(
        "fk_hr_employees_shift_id_shifts",
        "hr_employees",
        type_="foreignkey",
    )
    op.drop_column("hr_employees", "shift_id")
