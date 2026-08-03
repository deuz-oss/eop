"""add job grade id to hr employees

Revision ID: b3f7a1c9d2e4
Revises: 29f8159b5536
Create Date: 2026-08-03 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f7a1c9d2e4"
down_revision: str | Sequence[str] | None = "29f8159b5536"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("hr_employees", sa.Column("job_grade_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_hr_employees_job_grade_id_job_grades",
        "hr_employees",
        "job_grades",
        ["job_grade_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_hr_employees_job_grade_id", "hr_employees", ["job_grade_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_hr_employees_job_grade_id", table_name="hr_employees")
    op.drop_constraint(
        "fk_hr_employees_job_grade_id_job_grades", "hr_employees", type_="foreignkey"
    )
    op.drop_column("hr_employees", "job_grade_id")
