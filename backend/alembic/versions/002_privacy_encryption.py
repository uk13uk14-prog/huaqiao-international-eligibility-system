"""R4.3 Privacy: Add encrypted fields and blind indexes

Revision ID: 002_privacy
Revises: 001_initial
Create Date: 2026-01-17
"""
from alembic import op
import sqlalchemy as sa

revision = '002_privacy'
down_revision = '001_initial'
branch_labels = None
depends_on = None

def upgrade():
    # Add encrypted raw_input and blind indexes to eligibility_records
    with op.batch_alter_table('eligibility_records') as batch_op:
        batch_op.add_column(sa.Column('raw_input_encrypted', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('passport_blind_index', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('id_card_blind_index', sa.String(64), nullable=True))

    # Add encrypted fields and blind indexes to user_info
    with op.batch_alter_table('user_info') as batch_op:
        batch_op.add_column(sa.Column('passport_info_encrypted', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('household_info_encrypted', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('passport_blind_index', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('id_card_blind_index', sa.String(64), nullable=True))

def downgrade():
    with op.batch_alter_table('eligibility_records') as batch_op:
        batch_op.drop_column('passport_blind_index')
        batch_op.drop_column('id_card_blind_index')
        batch_op.drop_column('raw_input_encrypted')

    with op.batch_alter_table('user_info') as batch_op:
        batch_op.drop_column('passport_blind_index')
        batch_op.drop_column('id_card_blind_index')
        batch_op.drop_column('passport_info_encrypted')
        batch_op.drop_column('household_info_encrypted')
