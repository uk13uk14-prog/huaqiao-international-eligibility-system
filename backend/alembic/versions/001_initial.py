"""Initial migration - free backend

Revision ID: 001_initial
Revises:
Create Date: 2025-01-01
"""
from alembic import op
import sqlalchemy as sa

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_info',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('birth_date', sa.String(20), server_default=''),
        sa.Column('current_nationality', sa.String(80), server_default=''),
        sa.Column('has_chinese_nationality', sa.Boolean(), server_default='0'),
        sa.Column('has_foreign_nationality', sa.Boolean(), server_default='0'),
        sa.Column('passport_info', sa.Text(), server_default=''),
        sa.Column('household_info', sa.Text(), server_default=''),
        sa.Column('residence_records', sa.Text(), server_default='{}'),
        sa.Column('family_info', sa.Text(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'eligibility_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('user_info.id'), nullable=False),
        sa.Column('eligibility_type', sa.String(30), nullable=False, index=True),
        sa.Column('qualified', sa.Boolean(), nullable=False),
        sa.Column('conclusion', sa.String(200), nullable=False),
        sa.Column('reasons', sa.Text(), nullable=False),
        sa.Column('basis_articles', sa.Text(), nullable=False),
        sa.Column('suggestions', sa.Text(), server_default=''),
        sa.Column('raw_input', sa.Text(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table(
        'universities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(160), unique=True, nullable=False, index=True),
        sa.Column('ranking', sa.Integer(), server_default='999', index=True),
        sa.Column('province', sa.String(80), server_default=''),
        sa.Column('university_type', sa.String(80), server_default=''),
        sa.Column('target', sa.String(40), nullable=False, index=True),
        sa.Column('admission_targets', sa.String(120), server_default='huaqiao,international', index=True),
        sa.Column('tags', sa.String(200), server_default=''),
        sa.Column('fields', sa.String(200), server_default=''),
        sa.Column('advantage_majors', sa.Text(), server_default=''),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('requirements', sa.Text(), server_default=''),
        sa.Column('official_url', sa.String(300), server_default=''),
        sa.Column('admission_url', sa.String(300), server_default=''),
        sa.Column('admission_email', sa.String(160), server_default=''),
        sa.Column('admission_phone', sa.String(120), server_default=''),
        sa.Column('admissions_office', sa.String(160), server_default=''),
    )

    op.create_table(
        'admission_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('university_id', sa.Integer(), sa.ForeignKey('universities.id'), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False, index=True),
        sa.Column('month', sa.Integer(), nullable=False, index=True),
        sa.Column('registration_time', sa.String(160), server_default=''),
        sa.Column('material_deadline', sa.String(160), server_default=''),
        sa.Column('exam_time', sa.String(160), server_default=''),
        sa.Column('reminder', sa.Text(), server_default=''),
    )

    op.create_table(
        'app_clients',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_uuid', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('ping_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('app_version', sa.String(40), server_default=''),
        sa.Column('platform', sa.String(40), server_default=''),
        sa.Column('user_agent', sa.String(500), server_default=''),
    )

    op.create_table(
        'consultation_requests',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('client_uuid', sa.String(64), server_default='', index=True),
        sa.Column('name', sa.String(80), server_default=''),
        sa.Column('phone', sa.String(40), server_default=''),
        sa.Column('identity_type', sa.String(40), server_default=''),
        sa.Column('current_location', sa.String(120), server_default=''),
        sa.Column('education_background', sa.Text(), server_default=''),
        sa.Column('target_universities', sa.Text(), server_default=''),
        sa.Column('target_majors', sa.Text(), server_default=''),
        sa.Column('expected_enrollment_year', sa.String(20), server_default=''),
        sa.Column('notes', sa.Text(), server_default=''),
        sa.Column('status', sa.String(20), server_default='pending'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('consultation_requests')
    op.drop_table('app_clients')
    op.drop_table('admission_schedules')
    op.drop_table('universities')
    op.drop_table('eligibility_records')
    op.drop_table('user_info')
