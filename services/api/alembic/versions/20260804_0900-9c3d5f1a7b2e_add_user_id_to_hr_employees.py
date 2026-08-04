"""add user id to hr employees

Revision ID: 9c3d5f1a7b2e
Revises: f4a1c9e6b2d7
Create Date: 2026-08-04 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c3d5f1a7b2e"
down_revision: str | Sequence[str] | None = "f4a1c9e6b2d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("hr_employees", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_hr_employees_user_id_users",
        "hr_employees",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_hr_employees_user_id", "hr_employees", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_hr_employees_user_id", table_name="hr_employees")
    op.drop_constraint("fk_hr_employees_user_id_users", "hr_employees", type_="foreignkey")
    op.drop_column("hr_employees", "user_id")
