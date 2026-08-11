"""create field_attendance_events table

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-08-11 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2e3f4a5b6c7"
down_revision: str | Sequence[str] | None = "c1d2e3f4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "field_attendance_events",
        sa.Column("employee_id", sa.Uuid(), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum(
                "CHECK_IN",
                "CHECK_OUT",
                name="field_attendance_event_type",
                native_enum=False,
                length=20,
            ),
            nullable=False,
        ),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=False),
        sa.Column("gps_accuracy_meters", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("selfie_file_id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["employee_id"], ["hr_employees.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["selfie_file_id"], ["file_objects.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        "ix_field_attendance_events_employee_id",
        "field_attendance_events",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_field_attendance_events_event_type",
        "field_attendance_events",
        ["event_type"],
        unique=False,
    )
    op.create_index(
        "ix_field_attendance_events_event_time",
        "field_attendance_events",
        ["event_time"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_field_attendance_events_event_time", table_name="field_attendance_events")
    op.drop_index("ix_field_attendance_events_event_type", table_name="field_attendance_events")
    op.drop_index("ix_field_attendance_events_employee_id", table_name="field_attendance_events")
    op.drop_table("field_attendance_events")
