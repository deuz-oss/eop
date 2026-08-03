"""add employment type id to hr employees

Revision ID: 2b2c0e23e9bc
Revises: b3f7a1c9d2e4
Create Date: 2026-08-03 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2b2c0e23e9bc"
down_revision: str | Sequence[str] | None = "b3f7a1c9d2e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("hr_employees", sa.Column("employment_type_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_hr_employees_employment_type_id_employment_types",
        "hr_employees",
        "employment_types",
        ["employment_type_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_hr_employees_employment_type_id", "hr_employees", ["employment_type_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_hr_employees_employment_type_id", table_name="hr_employees")
    op.drop_constraint(
        "fk_hr_employees_employment_type_id_employment_types", "hr_employees", type_="foreignkey"
    )
    op.drop_column("hr_employees", "employment_type_id")
