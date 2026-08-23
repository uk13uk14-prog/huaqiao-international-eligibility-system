"""R4.3 FIX: Add encryption columns to eligibility_records

Revision ID: 003_r43_fix
Revises: 002_privacy_encryption
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = "003_r43_fix"
down_revision = "002_privacy_encryption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("eligibility_records", sa.Column("raw_input_encrypted", sa.Text, nullable=True))
    op.add_column("eligibility_records", sa.Column("passport_blind_index", sa.String(128), nullable=True))
    op.add_column("eligibility_records", sa.Column("id_card_blind_index", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("eligibility_records", "id_card_blind_index")
    op.drop_column("eligibility_records", "passport_blind_index")
    op.drop_column("eligibility_records", "raw_input_encrypted")
