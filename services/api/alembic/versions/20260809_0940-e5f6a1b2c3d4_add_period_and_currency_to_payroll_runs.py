"""add period and currency to payroll runs

Revision ID: e5f6a1b2c3d4
Revises: d4e5f6a1b2c3
Create Date: 2026-08-09 09:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a1b2c3d4"
down_revision: str | Sequence[str] | None = "d4e5f6a1b2c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Additive only: `period_start`/`period_end`/`currency` are nullable, so
    every existing `PayrollRun` row (Iteration 1-3) keeps `NULL` for all
    three -- an accepted historical gap, not a data-loss risk, mirroring
    the identical precedent already used for `Payslip.gross_salary_amount`/
    `net_salary_amount` (`models/payslip.py`). Every `PayrollRun` created
    going forward always populates all three, enforced by
    `PayrollRunCreate`/`PayrollRunService.create`, not by a `NOT NULL`
    constraint (`implementation-plan.md` §6).
    """
    op.add_column("payroll_runs", sa.Column("period_start", sa.Date(), nullable=True))
    op.add_column("payroll_runs", sa.Column("period_end", sa.Date(), nullable=True))
    op.add_column("payroll_runs", sa.Column("currency", sa.String(length=3), nullable=True))
    op.create_index(
        "ix_payroll_runs_period_currency",
        "payroll_runs",
        ["period_start", "period_end", "currency"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_payroll_runs_period_currency", table_name="payroll_runs")
    op.drop_column("payroll_runs", "currency")
    op.drop_column("payroll_runs", "period_end")
    op.drop_column("payroll_runs", "period_start")
