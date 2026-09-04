"""008 Notification Center V1 — DRAFT / NOT FOR PRODUCTION APPLY.

Revision ID: 008_notification_center_v1
Revises: 007_admin_ai_expert_v1

PROPOSAL ONLY:
  - Creates notifications, notification_rules, notification_devices, notification_preferences
  - Seeds default reminder rules (30/14/7/3/1/0 days)
  - Additive only; no drops; no backfill of secrets

Staging procedure (never production until explicit ops window):
  1. Backup staging DB
  2. alembic upgrade 007_admin_ai_expert_v1 → 008_notification_center_v1
  3. alembic downgrade -1
  4. alembic upgrade head
  5. Run pytest tests/test_notification_center_v1.py

Production apply: FORBIDDEN in this PR / cloud agent turn.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "008_notification_center_v1"
down_revision = "007_admin_ai_expert_v1"
branch_labels = None
depends_on = None

# Copy of this file may be promoted to alembic/versions/ only after staging PASS.


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recipient_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_role", sa.String(length=30), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("student_master_profiles.id"), nullable=True),
        sa.Column("category", sa.String(length=40), server_default="timeline"),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), server_default=""),
        sa.Column("source_type", sa.String(length=40), server_default=""),
        sa.Column("source_id", sa.String(length=120), server_default=""),
        sa.Column("scheduled_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="SCHEDULED"),
        sa.Column("priority", sa.String(length=20), server_default="NORMAL"),
        sa.Column("action_url", sa.String(length=400), server_default=""),
        sa.Column("action_label", sa.String(length=80), server_default=""),
        sa.Column("dedupe_key", sa.String(length=240), server_default=""),
        sa.Column("popup_shown_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notifications_recipient_user_id", "notifications", ["recipient_user_id"])
    op.create_index("ix_notifications_recipient_role", "notifications", ["recipient_role"])
    op.create_index("ix_notifications_student_id", "notifications", ["student_id"])
    op.create_index("ix_notifications_event_type", "notifications", ["event_type"])
    op.create_index("ix_notifications_status", "notifications", ["status"])
    op.create_index("ix_notifications_priority", "notifications", ["priority"])
    op.create_index("ix_notifications_scheduled_at", "notifications", ["scheduled_at"])
    op.create_index("ix_notifications_dedupe_key", "notifications", ["dedupe_key"])
    # Application-level dedupe is authoritative; DB unique is best-effort on dedupe_key+status.
    op.create_index(
        "ix_notifications_dedupe_status",
        "notifications",
        ["dedupe_key", "status"],
        unique=False,
    )

    op.create_table(
        "notification_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("days_before", sa.Integer(), nullable=True),
        sa.Column("hours_before", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("recipient_type", sa.String(length=30), nullable=False, server_default="STUDENT_SIDE"),
        sa.Column("priority", sa.String(length=20), server_default="NORMAL"),
        sa.Column("title_template", sa.String(length=240), server_default=""),
        sa.Column("body_template", sa.Text(), server_default=""),
        sa.Column("category", sa.String(length=40), server_default="timeline"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notification_rules_event_type", "notification_rules", ["event_type"])
    op.create_index("ix_notification_rules_enabled", "notification_rules", ["enabled"])

    op.create_table(
        "notification_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("device_type", sa.String(length=40), server_default="web"),
        sa.Column("platform", sa.String(length=40), server_default=""),
        sa.Column("push_provider", sa.String(length=20), server_default="IN_APP"),
        sa.Column("push_token_encrypted", sa.Text(), server_default=""),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_notification_devices_user_id", "notification_devices", ["user_id"])

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("timeline_enabled", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("expert_enabled", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("account_enabled", sa.Boolean(), server_default=sa.text("1")),
        sa.Column("quiet_hours_start", sa.String(length=8), server_default="22:00"),
        sa.Column("quiet_hours_end", sa.String(length=8), server_default="08:00"),
        sa.Column("timezone", sa.String(length=64), server_default="Asia/Shanghai"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", name="uq_notification_preferences_user_id"),
    )

    # Seed default APPLICATION_DEADLINE ladder (templates use {label} {days})
    rules = op.bulk_insert  # noqa: F841 — clarity
    nr = sa.table(
        "notification_rules",
        sa.column("event_type", sa.String),
        sa.column("days_before", sa.Integer),
        sa.column("hours_before", sa.Integer),
        sa.column("enabled", sa.Boolean),
        sa.column("recipient_type", sa.String),
        sa.column("priority", sa.String),
        sa.column("title_template", sa.String),
        sa.column("body_template", sa.Text),
        sa.column("category", sa.String),
    )
    ladder = [
        (30, "NORMAL", "距离{label}还有30天", "请提前规划材料与报名节奏。"),
        (14, "NORMAL", "距离{label}还有14天", "请确认申请材料是否齐全。"),
        (7, "HIGH", "申请截止仅剩7天：{label}", "建议今天完成材料最终核对。"),
        (3, "HIGH", "申请进入最后3天：{label}", "请立即确认提交状态。"),
        (1, "CRITICAL", "明天截止：{label}", "请马上确认是否已提交。"),
        (0, "CRITICAL", "今天是截止日：{label}", "请确认提交结果，如有问题立即联系顾问。"),
    ]
    rows = []
    for days, prio, title, body in ladder:
        rows.append(
            {
                "event_type": "APPLICATION_DEADLINE",
                "days_before": days,
                "hours_before": None,
                "enabled": True,
                "recipient_type": "STUDENT_SIDE",
                "priority": prio,
                "title_template": title,
                "body_template": body,
                "category": "timeline",
            }
        )
        rows.append(
            {
                "event_type": "APPLICATION_DEADLINE",
                "days_before": days,
                "hours_before": None,
                "enabled": True,
                "recipient_type": "ADMIN_SIDE",
                "priority": "HIGH" if days <= 7 else "NORMAL",
                "title_template": "学生重要截止临近（{days}天）：{label}",
                "body_template": "请关注学生进度与风险。",
                "category": "ops",
            }
        )
    # MATERIAL / EXAM lighter ladders
    for et, cat in (("MATERIAL_DEADLINE", "timeline"), ("EXAM_DATE", "timeline"), ("INTERVIEW_DATE", "timeline")):
        for days, prio in ((14, "NORMAL"), (7, "HIGH"), (3, "HIGH"), (1, "CRITICAL"), (0, "CRITICAL")):
            rows.append(
                {
                    "event_type": et,
                    "days_before": days,
                    "hours_before": None,
                    "enabled": True,
                    "recipient_type": "STUDENT_SIDE",
                    "priority": prio,
                    "title_template": f"{{label}}还有{{days}}天",
                    "body_template": "请查看时间线并完成对应任务。",
                    "category": cat,
                }
            )
    op.bulk_insert(nr, rows)


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_table("notification_devices")
    op.drop_table("notification_rules")
    op.drop_index("ix_notifications_dedupe_status", table_name="notifications")
    op.drop_index("ix_notifications_dedupe_key", table_name="notifications")
    op.drop_index("ix_notifications_scheduled_at", table_name="notifications")
    op.drop_index("ix_notifications_priority", table_name="notifications")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_event_type", table_name="notifications")
    op.drop_index("ix_notifications_student_id", table_name="notifications")
    op.drop_index("ix_notifications_recipient_role", table_name="notifications")
    op.drop_index("ix_notifications_recipient_user_id", table_name="notifications")
    op.drop_table("notifications")
