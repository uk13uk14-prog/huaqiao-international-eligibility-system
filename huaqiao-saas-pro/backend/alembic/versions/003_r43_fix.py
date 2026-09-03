"""R4.3 FIX: Add permissions to User, encryption columns to EligibilityRecord

Revision ID: 003_r43_fix
Revises: 002_privacy
Create Date: 2025-01-01

Freeze repair note:
- down_revision must match 002 file's revision id (`002_privacy`), not the filename.
- encryption columns may already exist from 002; add them idempotently.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.types import JSON

revision = "003_r43_fix"
down_revision = "002_privacy"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("users", "permissions"):
        op.add_column("users", sa.Column("permissions", JSON, nullable=True, server_default="[]"))

    # Idempotent: 002_privacy may already have added these.
    if not _has_column("eligibility_records", "raw_input_encrypted"):
        op.add_column("eligibility_records", sa.Column("raw_input_encrypted", sa.Text, nullable=True))
    if not _has_column("eligibility_records", "passport_blind_index"):
        op.add_column("eligibility_records", sa.Column("passport_blind_index", sa.String(128), nullable=True))
    if not _has_column("eligibility_records", "id_card_blind_index"):
        op.add_column("eligibility_records", sa.Column("id_card_blind_index", sa.String(128), nullable=True))


def downgrade() -> None:
    # Only drop permissions here; encryption columns belong to 002_privacy.
    if _has_column("users", "permissions"):
        op.drop_column("users", "permissions")
