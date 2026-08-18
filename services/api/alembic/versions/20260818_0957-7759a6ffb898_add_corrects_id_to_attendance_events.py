"""add corrects_id to attendance_events

Revision ID: 7759a6ffb898
Revises: 42e2f3e3d810
Create Date: 2026-08-18 09:57:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7759a6ffb898"
down_revision: str | Sequence[str] | None = "42e2f3e3d810"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Additive only: `corrects_id` is nullable, so every existing row
    receives NULL (an ordinary event, not a correction) -- no existing data
    is reinterpreted. Mirrors `compensations.corrects_id`'s exact shape
    (nullable self-referencing FK, `ON DELETE RESTRICT`) -- AttendanceEvent
    Integrity workstream: historical attendance events are corrected via a
    new linked row, never mutated or deleted in place.
    """
    op.add_column("attendance_events", sa.Column("corrects_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_attendance_events_corrects_id_attendance_events",
        "attendance_events",
        "attendance_events",
        ["corrects_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_attendance_events_corrects_id", "attendance_events", ["corrects_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema.

    Reverses only this migration's own changes. Any correction relation
    recorded via `corrects_id` is lost on downgrade -- an inherent
    consequence of removing the column, not a new data-loss behavior
    introduced beyond that.
    """
    op.drop_index("ix_attendance_events_corrects_id", table_name="attendance_events")
    op.drop_constraint(
        "fk_attendance_events_corrects_id_attendance_events",
        "attendance_events",
        type_="foreignkey",
    )
    op.drop_column("attendance_events", "corrects_id")
