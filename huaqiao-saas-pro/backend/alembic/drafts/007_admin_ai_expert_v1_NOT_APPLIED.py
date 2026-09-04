"""DRAFT ONLY — NOT APPLIED — DO NOT RUN ON PRODUCTION.

Revision ID: 007_admin_ai_expert_v1 (DRAFT)
Revises: 006_student_profile_slots

Status:
  MIGRATION_APPLIED = NO
  PRODUCTION_DB_CHANGED = NO

Rules for this draft:
  - upgrade: ONLY add nullable columns / indexes / new audit_events table
  - NO drop of existing columns/tables
  - NO rewrite / mass update / guessed student_id backfill
  - downgrade: reverse only what this revision adds

This file lives under alembic/drafts/ (NOT alembic/versions/) so Alembic
will not auto-pick it. Copy into versions/ only after explicit staging approval.
"""
from alembic import op
import sqlalchemy as sa

revision = "007_admin_ai_expert_v1"
down_revision = "006_student_profile_slots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- expert_consultations: bind to student + AI metadata (all nullable / additive) ---
    op.add_column(
        "expert_consultations",
        sa.Column("student_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_expert_consultations_student_id", "expert_consultations", ["student_id"])
    op.create_foreign_key(
        "fk_expert_consultations_student_id",
        "expert_consultations",
        "student_master_profiles",
        ["student_id"],
        ["id"],
    )
    op.add_column(
        "expert_consultations",
        sa.Column("assigned_consultant_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_expert_consultations_assigned_consultant",
        "expert_consultations",
        "users",
        ["assigned_consultant_id"],
        ["id"],
    )
    # provider (ai_provider); model column ai_model already exists
    op.add_column("expert_consultations", sa.Column("ai_provider", sa.String(length=40), nullable=True))
    op.add_column("expert_consultations", sa.Column("report_kind", sa.String(length=60), nullable=True))
    op.add_column("expert_consultations", sa.Column("payload_json", sa.Text(), nullable=True))
    # status column already exists — Admin V1 uses DRAFT/REVIEWED/APPROVED/PUBLISHED/ARCHIVED
    # alongside legacy pending_ai/draft_ready/published. No enum rewrite.

    # --- eligibility_records: optional student binding (no backfill) ---
    op.add_column(
        "eligibility_records",
        sa.Column("student_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_eligibility_records_student_id", "eligibility_records", ["student_id"])
    op.create_foreign_key(
        "fk_eligibility_records_student_id",
        "eligibility_records",
        "student_master_profiles",
        ["student_id"],
        ["id"],
    )

    # --- durable audit events ---
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("action", sa.String(length=80), nullable=False, index=True),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_master_profiles.id"), nullable=True, index=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_constraint("fk_eligibility_records_student_id", "eligibility_records", type_="foreignkey")
    op.drop_index("ix_eligibility_records_student_id", table_name="eligibility_records")
    op.drop_column("eligibility_records", "student_id")
    op.drop_constraint("fk_expert_consultations_assigned_consultant", "expert_consultations", type_="foreignkey")
    op.drop_constraint("fk_expert_consultations_student_id", "expert_consultations", type_="foreignkey")
    op.drop_index("ix_expert_consultations_student_id", table_name="expert_consultations")
    op.drop_column("expert_consultations", "payload_json")
    op.drop_column("expert_consultations", "report_kind")
    op.drop_column("expert_consultations", "ai_provider")
    op.drop_column("expert_consultations", "assigned_consultant_id")
    op.drop_column("expert_consultations", "student_id")
