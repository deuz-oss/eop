"""create work schedules table

Revision ID: a7b8c9d0e1f2
Revises: f6a1b2c3d4e5
Create Date: 2026-08-09 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: str | Sequence[str] | None = "f6a1b2c3d4e5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "work_schedules",
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("shift_id", sa.Uuid(), nullable=False),
        sa.Column("works_monday", sa.Boolean(), nullable=False),
        sa.Column("works_tuesday", sa.Boolean(), nullable=False),
        sa.Column("works_wednesday", sa.Boolean(), nullable=False),
        sa.Column("works_thursday", sa.Boolean(), nullable=False),
        sa.Column("works_friday", sa.Boolean(), nullable=False),
        sa.Column("works_saturday", sa.Boolean(), nullable=False),
        sa.Column("works_sunday", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("corrects_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["employee_id"], ["hr_employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["shift_id"], ["shifts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["corrects_id"],
            ["work_schedules.id"],
            ondelete="RESTRICT",
            name="fk_work_schedules_corrects_id_work_schedules",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_schedules_employee_effective",
        "work_schedules",
        ["employee_id", "effective_from"],
        unique=False,
    )
    op.create_index(
        "ix_work_schedules_corrects_id", "work_schedules", ["corrects_id"], unique=False
    )
    op.create_index("ix_work_schedules_shift_id", "work_schedules", ["shift_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_work_schedules_shift_id", table_name="work_schedules")
    op.drop_index("ix_work_schedules_corrects_id", table_name="work_schedules")
    op.drop_index("ix_work_schedules_employee_effective", table_name="work_schedules")
    op.drop_table("work_schedules")
