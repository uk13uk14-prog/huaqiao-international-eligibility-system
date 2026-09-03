"""Alembic: Student Master Profile v2 table.

Revision ID: 004_student_master_profile
Revises: 003_r43_fix
"""
from alembic import op
import sqlalchemy as sa

revision = "004_student_master_profile"
down_revision = "003_r43_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_master_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("display_name", sa.String(160), server_default=""),
        sa.Column("cipher_blob", sa.Text(), server_default=""),
        sa.Column("schema_version", sa.Integer(), server_default="2"),
        sa.Column("source", sa.String(40), server_default="created"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("student_master_profiles")
