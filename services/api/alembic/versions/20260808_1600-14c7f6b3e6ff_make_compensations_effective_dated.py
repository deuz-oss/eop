"""make compensations effective-dated (multi-row per employee)

Revision ID: 14c7f6b3e6ff
Revises: d2f6a4c8b193
Create Date: 2026-08-08 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "14c7f6b3e6ff"
down_revision: str | Sequence[str] | None = "d2f6a4c8b193"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Additive only: existing `Compensation` rows keep every current value.
    `effective_to` is nullable -- every existing row receives NULL
    (open-ended, still effective), not an inferred date.
    `uq_compensations_employee_id` is dropped because
    `docs/architecture/capabilities/compensation/decision.md` §17
    (Accepted) requires multiple rows per employee; no replacement
    uniqueness/overlap constraint is added, since overlap permission
    remains an open Business/Product decision (§7).
    """
    op.add_column("compensations", sa.Column("effective_to", sa.Date(), nullable=True))
    op.drop_constraint("uq_compensations_employee_id", "compensations", type_="unique")
    op.drop_index("ix_compensations_employee_id", table_name="compensations")
    op.create_index(
        "ix_compensations_employee_effective",
        "compensations",
        ["employee_id", "effective_from"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema.

    Reverses only this migration's own changes. Note: any `effective_to`
    values written after this migration upgraded are lost on downgrade --
    an inherent property of removing an added column, not a new data-loss
    behavior introduced by this migration for pre-existing data.
    """
    op.drop_index("ix_compensations_employee_effective", table_name="compensations")
    op.create_index("ix_compensations_employee_id", "compensations", ["employee_id"], unique=False)
    op.create_unique_constraint("uq_compensations_employee_id", "compensations", ["employee_id"])
    op.drop_column("compensations", "effective_to")
