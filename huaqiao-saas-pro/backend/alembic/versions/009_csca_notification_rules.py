"""009 CSCA notification rules (staging draft).

Revision ID: 009_csca_notification_rules
Revises: 008_notification_center_v1

Additive only: seeds CSCA reminder rules (T-30/14/7/3/1/0).
NO production apply in this agent turn.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "009_csca_notification_rules"
down_revision = "008_notification_center_v1"
branch_labels = None
depends_on = None

CSCA_EVENT_TYPES = (
    "CSCA_REGISTRATION_DEADLINE",
    "CSCA_EXAM_DATE",
    "CSCA_RESULT_DATE",
    "CSCA_PREPARATION",
)

LADDER = (
    (30, "NORMAL", "距离{label}还有30天", "请提前准备 CSCA 相关材料与复习计划。"),
    (14, "NORMAL", "距离{label}还有14天", "请确认报名/考试安排是否就绪。"),
    (7, "HIGH", "CSCA 节点仅剩7天：{label}", "建议完成本周备考与材料核对。"),
    (3, "HIGH", "CSCA 进入最后3天：{label}", "请立即确认状态与行程。"),
    (1, "CRITICAL", "明天是 CSCA 节点：{label}", "请马上确认是否已完成对应事项。"),
    (0, "CRITICAL", "今天是 CSCA 节点：{label}", "请确认结果，如有问题联系顾问。"),
)


def upgrade() -> None:
    conn = op.get_bind()
    rules = sa.table(
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
    existing = {
        (r[0], r[1], r[2])
        for r in conn.execute(
            sa.text(
                "SELECT event_type, days_before, recipient_type FROM notification_rules "
                "WHERE event_type LIKE 'CSCA_%'"
            )
        )
    }
    rows = []
    for et in CSCA_EVENT_TYPES:
        for days, prio, title, body in LADDER:
            key = (et, days, "STUDENT_SIDE")
            if key in existing:
                continue
            rows.append(
                {
                    "event_type": et,
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
    if rows:
        op.bulk_insert(rules, rows)


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM notification_rules WHERE event_type IN "
            "('CSCA_REGISTRATION_DEADLINE','CSCA_EXAM_DATE','CSCA_RESULT_DATE','CSCA_PREPARATION')"
        )
    )
