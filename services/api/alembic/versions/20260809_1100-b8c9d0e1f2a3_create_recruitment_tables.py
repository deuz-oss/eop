"""create recruitment tables

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-09 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b8c9d0e1f2a3"
down_revision: str | Sequence[str] | None = "a7b8c9d0e1f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _audit_columns() -> list[sa.Column]:
    """The `BaseEntity` mixin column set, shared by every table this
    migration creates -- matches every other model migration in this
    repository (e.g. `create_work_schedules_table`)."""
    return [
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
    ]


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "job_requisitions",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("department_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("description", sa.String(length=2000), nullable=True),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_job_requisitions_code"),
    )
    op.create_index(
        "ix_job_requisitions_organization_id", "job_requisitions", ["organization_id"], unique=False
    )
    op.create_index(
        "ix_job_requisitions_department_id", "job_requisitions", ["department_id"], unique=False
    )
    op.create_index(
        "ix_job_requisitions_position_id", "job_requisitions", ["position_id"], unique=False
    )
    op.create_index("ix_job_requisitions_status", "job_requisitions", ["status"], unique=False)

    op.create_table(
        "candidates",
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        *_audit_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_candidates_email"),
    )

    op.create_table(
        "applications",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("job_requisition_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("applied_date", sa.Date(), nullable=False),
        *_audit_columns(),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["job_requisition_id"], ["job_requisitions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id",
            "job_requisition_id",
            name="uq_applications_candidate_id_job_requisition_id",
        ),
    )
    op.create_index("ix_applications_candidate_id", "applications", ["candidate_id"], unique=False)
    op.create_index(
        "ix_applications_job_requisition_id", "applications", ["job_requisition_id"], unique=False
    )
    op.create_index("ix_applications_status", "applications", ["status"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_applications_status", table_name="applications")
    op.drop_index("ix_applications_job_requisition_id", table_name="applications")
    op.drop_index("ix_applications_candidate_id", table_name="applications")
    op.drop_table("applications")

    op.drop_table("candidates")

    op.drop_index("ix_job_requisitions_status", table_name="job_requisitions")
    op.drop_index("ix_job_requisitions_position_id", table_name="job_requisitions")
    op.drop_index("ix_job_requisitions_department_id", table_name="job_requisitions")
    op.drop_index("ix_job_requisitions_organization_id", table_name="job_requisitions")
    op.drop_table("job_requisitions")
