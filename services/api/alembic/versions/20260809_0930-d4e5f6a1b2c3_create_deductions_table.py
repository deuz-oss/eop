"""create deductions table

Revision ID: d4e5f6a1b2c3
Revises: c3d4e5f6a1b2
Create Date: 2026-08-09 09:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a1b2c3"
down_revision: str | Sequence[str] | None = "c3d4e5f6a1b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "deductions",
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("deduction_type_id", sa.Uuid(), nullable=False),
        sa.Column("payroll_run_id", sa.Uuid(), nullable=False),
        sa.Column("deduction_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("deduction_currency", sa.String(length=3), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
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
        sa.ForeignKeyConstraint(["deduction_type_id"], ["deduction_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payroll_run_id"], ["payroll_runs.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deductions_employee_id", "deductions", ["employee_id"], unique=False)
    op.create_index("ix_deductions_payroll_run_id", "deductions", ["payroll_run_id"], unique=False)
    op.create_index(
        "ix_deductions_deduction_type_id", "deductions", ["deduction_type_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_deductions_deduction_type_id", table_name="deductions")
    op.drop_index("ix_deductions_payroll_run_id", table_name="deductions")
    op.drop_index("ix_deductions_employee_id", table_name="deductions")
    op.drop_table("deductions")
