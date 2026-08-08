"""create payslip line items table

Revision ID: f6a1b2c3d4e5
Revises: e5f6a1b2c3d4
Create Date: 2026-08-09 09:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a1b2c3d4e5"
down_revision: str | Sequence[str] | None = "e5f6a1b2c3d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "payslip_line_items",
        sa.Column("payslip_id", sa.Uuid(), nullable=False),
        sa.Column(
            "component_type",
            sa.Enum(
                "BASE_SALARY",
                "ALLOWANCE",
                "OVERTIME",
                "ATTENDANCE_DEDUCTION",
                "LEAVE_DEDUCTION",
                "STATUTORY_DEDUCTION",
                "NON_STATUTORY_DEDUCTION",
                name="payslip_line_item_type",
                native_enum=False,
                length=30,
            ),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("line_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("line_currency", sa.String(length=3), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["payslip_id"], ["payslips.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_payslip_line_items_payslip_id", "payslip_line_items", ["payslip_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_payslip_line_items_payslip_id", table_name="payslip_line_items")
    op.drop_table("payslip_line_items")
