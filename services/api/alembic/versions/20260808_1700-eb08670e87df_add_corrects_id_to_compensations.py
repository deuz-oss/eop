"""add corrects_id to compensations

Revision ID: eb08670e87df
Revises: 14c7f6b3e6ff
Create Date: 2026-08-08 17:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eb08670e87df"
down_revision: str | Sequence[str] | None = "14c7f6b3e6ff"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Additive only: `corrects_id` is nullable, so every existing row
    receives NULL (an ordinary row, not a correction) -- no existing data
    is reinterpreted. `docs/architecture/capabilities/compensation/decision.md`
    §19 (Accepted, Option C2b): self-referencing FK, mirrors
    `Department.parent_id`/`HrEmployee.manager_id`'s exact shape
    (nullable, `ON DELETE RESTRICT`).
    """
    op.add_column("compensations", sa.Column("corrects_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_compensations_corrects_id_compensations",
        "compensations",
        "compensations",
        ["corrects_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_compensations_corrects_id", "compensations", ["corrects_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema.

    Reverses only this migration's own changes. Any correction relation
    recorded via `corrects_id` is lost on downgrade -- an inherent
    consequence of removing the column, not a new data-loss behavior
    introduced beyond that.
    """
    op.drop_index("ix_compensations_corrects_id", table_name="compensations")
    op.drop_constraint(
        "fk_compensations_corrects_id_compensations", "compensations", type_="foreignkey"
    )
    op.drop_column("compensations", "corrects_id")
