"""010 Student CRM V1 — assignee + follow-ups + ops fields.

Revision ID: 010_student_crm_v1
Revises: 009_csca_notification_rules

Additive only (staging first). NO production apply in this agent turn.
- student_master_profiles: CRM ops columns (assignee, stage, next action)
- student_follow_ups: follow-up / activity log
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "010_student_crm_v1"
down_revision = "009_csca_notification_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "student_master_profiles",
        sa.Column("assignee_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.create_index("ix_student_master_profiles_assignee_user_id", "student_master_profiles", ["assignee_user_id"])
    op.add_column(
        "student_master_profiles",
        sa.Column("assigned_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "student_master_profiles",
        sa.Column("assigned_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "student_master_profiles",
        sa.Column("crm_stage", sa.String(length=40), server_default="UNASSIGNED", nullable=False),
    )
    op.create_index("ix_student_master_profiles_crm_stage", "student_master_profiles", ["crm_stage"])
    op.add_column(
        "student_master_profiles",
        sa.Column("risk_level", sa.String(length=20), server_default="NONE", nullable=False),
    )
    op.add_column(
        "student_master_profiles",
        sa.Column("next_action", sa.Text(), server_default="", nullable=False),
    )
    op.add_column(
        "student_master_profiles",
        sa.Column("next_follow_up_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_student_master_profiles_next_follow_up_at",
        "student_master_profiles",
        ["next_follow_up_at"],
    )
    op.add_column(
        "student_master_profiles",
        sa.Column("last_follow_up_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "student_master_profiles",
        sa.Column("identity_track", sa.String(length=40), server_default="", nullable=False),
    )

    op.create_table(
        "student_follow_ups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_master_profiles.id"), nullable=False, index=True),
        sa.Column("operator_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("operator_type", sa.String(length=20), server_default="HUMAN", nullable=False),
        sa.Column("source", sa.String(length=20), server_default="HUMAN", nullable=False),
        sa.Column("type", sa.String(length=40), server_default="NOTE", nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("summary", sa.String(length=240), server_default="", nullable=False),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("next_follow_up_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_student_follow_ups_created_at", "student_follow_ups", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_student_follow_ups_created_at", table_name="student_follow_ups")
    op.drop_table("student_follow_ups")
    op.drop_index("ix_student_master_profiles_next_follow_up_at", table_name="student_master_profiles")
    op.drop_index("ix_student_master_profiles_crm_stage", table_name="student_master_profiles")
    op.drop_index("ix_student_master_profiles_assignee_user_id", table_name="student_master_profiles")
    op.drop_column("student_master_profiles", "identity_track")
    op.drop_column("student_master_profiles", "last_follow_up_at")
    op.drop_column("student_master_profiles", "next_follow_up_at")
    op.drop_column("student_master_profiles", "next_action")
    op.drop_column("student_master_profiles", "risk_level")
    op.drop_column("student_master_profiles", "crm_stage")
    op.drop_column("student_master_profiles", "assigned_by_user_id")
    op.drop_column("student_master_profiles", "assigned_at")
    op.drop_column("student_master_profiles", "assignee_user_id")
