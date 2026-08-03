"""add employment status id to hr employees

Revision ID: 2fe575272108
Revises: 2b2c0e23e9bc
Create Date: 2026-08-03 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2fe575272108"
down_revision: str | Sequence[str] | None = "2b2c0e23e9bc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("hr_employees", sa.Column("employment_status_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_hr_employees_employment_status_id_employment_statuses",
        "hr_employees",
        "employment_statuses",
        ["employment_status_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_hr_employees_employment_status_id",
        "hr_employees",
        ["employment_status_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_hr_employees_employment_status_id", table_name="hr_employees")
    op.drop_constraint(
        "fk_hr_employees_employment_status_id_employment_statuses",
        "hr_employees",
        type_="foreignkey",
    )
    op.drop_column("hr_employees", "employment_status_id")
