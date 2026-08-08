"""create allowances table

Revision ID: b2c3d4e5f6a1
Revises: a1b2c3d4e5f6
Create Date: 2026-08-09 09:10:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a1"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "allowances",
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column("allowance_type", sa.String(length=50), nullable=False),
        sa.Column("allowance_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("allowance_currency", sa.String(length=3), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["corrects_id"],
            ["allowances.id"],
            ondelete="RESTRICT",
            name="fk_allowances_corrects_id_allowances",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_allowances_employee_type_effective",
        "allowances",
        ["employee_id", "allowance_type", "effective_from"],
        unique=False,
    )
    op.create_index("ix_allowances_corrects_id", "allowances", ["corrects_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_allowances_corrects_id", table_name="allowances")
    op.drop_index("ix_allowances_employee_type_effective", table_name="allowances")
    op.drop_table("allowances")
