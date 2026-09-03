"""Alembic: student personalized timeline items.

Revision ID: 005_student_timeline
Revises: 004_student_master_profile
"""
from alembic import op
import sqlalchemy as sa

revision = "005_student_timeline"
down_revision = "004_student_master_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_timeline_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_master_profiles.id"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("source_timeline_id", sa.Integer(), sa.ForeignKey("admission_schedules.id"), nullable=True, index=True),
        sa.Column("title", sa.String(240), server_default=""),
        sa.Column("description", sa.Text(), server_default=""),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True, index=True),
        sa.Column("university_id", sa.Integer(), sa.ForeignKey("universities.id"), nullable=True),
        sa.Column("university_name", sa.String(160), server_default=""),
        sa.Column("entry_year", sa.Integer(), nullable=True),
        sa.Column("application_route", sa.String(40), server_default=""),
        sa.Column("status", sa.String(30), server_default="NOT_STARTED", index=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("student_note", sa.Text(), server_default=""),
        sa.Column("is_manual", sa.Boolean(), server_default=sa.false(), index=True),
        sa.Column("needs_confirmation", sa.Boolean(), server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("student_timeline_items")
