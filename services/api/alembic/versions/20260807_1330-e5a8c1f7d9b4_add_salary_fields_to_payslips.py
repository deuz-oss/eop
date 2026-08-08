"""add gross and net salary fields to payslips

Revision ID: e5a8c1f7d9b4
Revises: b7e21f4a9c3d
Create Date: 2026-08-07 13:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a8c1f7d9b4"
down_revision: str | Sequence[str] | None = "b7e21f4a9c3d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MONEY_COLUMNS = (
    ("gross_salary_amount", sa.Numeric(precision=14, scale=2)),
    ("gross_salary_currency", sa.String(length=3)),
    ("net_salary_amount", sa.Numeric(precision=14, scale=2)),
    ("net_salary_currency", sa.String(length=3)),
)


def upgrade() -> None:
    """Upgrade schema."""
    for name, col_type in _MONEY_COLUMNS:
        op.add_column("payslips", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for name, _ in reversed(_MONEY_COLUMNS):
        op.drop_column("payslips", name)
