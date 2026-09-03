"""Alembic: student profile soft-delete + seat override.

Revision ID: 006_student_profile_slots
Revises: 005_student_timeline
"""
from alembic import op
import sqlalchemy as sa

revision = "006_student_profile_slots"
down_revision = "005_student_timeline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_master_profiles",
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
    )
    op.create_index("ix_student_master_profiles_status", "student_master_profiles", ["status"])
    op.add_column("student_master_profiles", sa.Column("archived_at", sa.DateTime(), nullable=True))
    op.add_column("student_master_profiles", sa.Column("deleted_at", sa.DateTime(), nullable=True))

    op.add_column("users", sa.Column("student_profile_limit_override", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "student_profile_limit_override")
    op.drop_column("student_master_profiles", "deleted_at")
    op.drop_column("student_master_profiles", "archived_at")
    op.drop_index("ix_student_master_profiles_status", table_name="student_master_profiles")
    op.drop_column("student_master_profiles", "status")
