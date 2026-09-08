"""012 Cooperation Center V1 — settings + brands.

Revision ID: 012_cooperation_center_v1
Revises: 011_admin_console_v2

Additive only. Do not apply to production in this PR.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "012_cooperation_center_v1"
down_revision = "011_admin_console_v2"
branch_labels = None
depends_on = None


def _tables() -> set[str]:
    bind = op.get_bind()
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    tables = _tables()
    if "cooperation_settings" not in tables:
        op.create_table(
            "cooperation_settings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("page_title", sa.String(length=120), nullable=True),
            sa.Column("intro", sa.Text(), nullable=True),
            sa.Column("contact_name", sa.String(length=80), nullable=True),
            sa.Column("wechat", sa.String(length=80), nullable=True),
            sa.Column("phone", sa.String(length=80), nullable=True),
            sa.Column("email", sa.String(length=160), nullable=True),
            sa.Column("contact_note", sa.Text(), nullable=True),
            sa.Column("qr_image_url", sa.String(length=500), nullable=True),
            sa.Column("show_contact_name", sa.Boolean(), nullable=True),
            sa.Column("show_wechat", sa.Boolean(), nullable=True),
            sa.Column("show_phone", sa.Boolean(), nullable=True),
            sa.Column("show_email", sa.Boolean(), nullable=True),
            sa.Column("show_contact_note", sa.Boolean(), nullable=True),
            sa.Column("show_qr", sa.Boolean(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
    if "cooperation_brands" not in tables:
        op.create_table(
            "cooperation_brands",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("brand_name", sa.String(length=160), nullable=False),
            sa.Column("logo_url", sa.String(length=500), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("link", sa.String(length=400), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_cooperation_brands_sort_order", "cooperation_brands", ["sort_order"])
        op.create_index("ix_cooperation_brands_is_active", "cooperation_brands", ["is_active"])


def downgrade() -> None:
    tables = _tables()
    if "cooperation_brands" in tables:
        op.drop_index("ix_cooperation_brands_is_active", table_name="cooperation_brands")
        op.drop_index("ix_cooperation_brands_sort_order", table_name="cooperation_brands")
        op.drop_table("cooperation_brands")
    if "cooperation_settings" in tables:
        op.drop_table("cooperation_settings")
