"""create visit_photos table

Revision ID: e3f4a5b6c7d8
Revises: d2e3f4a5b6c7
Create Date: 2026-08-11 13:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e3f4a5b6c7d8"
down_revision: str | Sequence[str] | None = "d2e3f4a5b6c7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "visit_photos",
        sa.Column("visit_id", sa.Uuid(), nullable=False),
        sa.Column("file_object_id", sa.Uuid(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["visit_id"], ["visits.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["file_object_id"], ["file_objects.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_visit_photos_visit_id", "visit_photos", ["visit_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_visit_photos_visit_id", table_name="visit_photos")
    op.drop_table("visit_photos")
