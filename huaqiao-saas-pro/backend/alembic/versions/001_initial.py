"""Initial migration - saas-pro backend

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
        'tenants',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('tenant_type', sa.String(30), server_default='personal'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('email', sa.String(160), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(80), server_default=''),
        sa.Column('password_hash', sa.String(160), nullable=False),
        sa.Column('role', sa.String(30), server_default='member'),
        sa.Column('plan_code', sa.String(40), server_default='free', index=True),
        sa.Column('membership_until', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'auth_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('token', sa.String(512), unique=True, nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'membership_plans',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(40), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(80), nullable=False),
        sa.Column('price', sa.Integer(), server_default='0'),
        sa.Column('duration_days', sa.Integer(), server_default='0'),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('features', sa.Text(), server_default='{}'),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
    )

    op.create_table(
        'orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('plan_code', sa.String(40), nullable=False, index=True),
        sa.Column('amount', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(30), server_default='paid'),
        sa.Column('source', sa.String(30), server_default='redeem_code'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'payment_orders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_no', sa.String(80), unique=True, nullable=False, index=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('plan_code', sa.String(40), nullable=False, index=True),
        sa.Column('channel', sa.String(30), nullable=False, index=True),
        sa.Column('amount', sa.Integer(), server_default='0'),
        sa.Column('status', sa.String(30), server_default='pending', index=True),
        sa.Column('pay_url', sa.Text(), server_default=''),
        sa.Column('qr_content', sa.Text(), server_default=''),
        sa.Column('provider_trade_no', sa.String(120), server_default=''),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'recharge_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(80), unique=True, nullable=False, index=True),
        sa.Column('plan_code', sa.String(40), nullable=False, index=True),
        sa.Column('duration_days', sa.Integer(), server_default='30'),
        sa.Column('is_used', sa.Boolean(), server_default='0'),
        sa.Column('used_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'permission_configs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plan_code', sa.String(40), unique=True, nullable=False, index=True),
        sa.Column('config', sa.Text(), server_default='{}'),
    )

    op.create_table(
        'eligibility_records',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('eligibility_type', sa.String(30), nullable=False, index=True),
        sa.Column('qualified', sa.Boolean(), nullable=False),
        sa.Column('conclusion', sa.String(200), nullable=False),
        sa.Column('reasons', sa.Text(), server_default='[]'),
        sa.Column('basis_articles', sa.Text(), server_default='[]'),
        sa.Column('recommendations', sa.Text(), server_default='[]'),
        sa.Column('suggestions', sa.Text(), server_default='[]'),
        sa.Column('raw_input', sa.Text(), server_default='{}'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table(
        'universities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('ranking', sa.Integer(), server_default='999', index=True),
        sa.Column('name', sa.String(160), unique=True, nullable=False, index=True),
        sa.Column('province', sa.String(80), server_default=''),
        sa.Column('university_type', sa.String(120), server_default=''),
        sa.Column('tags', sa.String(200), server_default=''),
        sa.Column('fields', sa.String(200), server_default=''),
        sa.Column('admission_targets', sa.String(120), server_default='international,huaqiao'),
        sa.Column('advantage_majors', sa.Text(), server_default=''),
        sa.Column('description', sa.Text(), server_default=''),
        sa.Column('requirements', sa.Text(), server_default=''),
        sa.Column('official_url', sa.String(300), server_default=''),
        sa.Column('admission_url', sa.String(300), server_default=''),
        sa.Column('admission_email', sa.String(160), server_default=''),
        sa.Column('admission_phone', sa.String(120), server_default=''),
        sa.Column('admissions_office', sa.String(160), server_default=''),
        sa.Column('is_core', sa.Boolean(), server_default='1', index=True),
    )

    op.create_table(
        'admission_schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('university_id', sa.Integer(), sa.ForeignKey('universities.id'), nullable=False, index=True),
        sa.Column('year', sa.Integer(), server_default='2026'),
        sa.Column('month', sa.Integer(), server_default='1', index=True),
        sa.Column('registration_time', sa.String(160), server_default=''),
        sa.Column('material_deadline', sa.String(160), server_default=''),
        sa.Column('exam_time', sa.String(160), server_default=''),
        sa.Column('reminder', sa.Text(), server_default=''),
    )

    op.create_table(
        'customer_vaults',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, unique=True, index=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('cipher_blob', sa.Text(), server_default=''),
        sa.Column('schema_version', sa.Integer(), server_default='1'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'expert_consultations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('title', sa.String(200), server_default=''),
        sa.Column('question', sa.Text(), server_default=''),
        sa.Column('personalization', sa.Text(), server_default=''),
        sa.Column('contact_phone', sa.String(40), server_default=''),
        sa.Column('contact_email', sa.String(160), server_default=''),
        sa.Column('contact_wechat', sa.String(80), server_default=''),
        sa.Column('status', sa.String(30), server_default='pending_ai', index=True),
        sa.Column('ai_draft', sa.Text(), server_default=''),
        sa.Column('ai_model', sa.String(120), server_default=''),
        sa.Column('final_report', sa.Text(), server_default=''),
        sa.Column('admin_note', sa.Text(), server_default=''),
        sa.Column('reviewed_by_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )

    op.create_table(
        'consultation_report_versions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('consultation_id', sa.Integer(), sa.ForeignKey('expert_consultations.id'), nullable=False, index=True),
        sa.Column('version_no', sa.Integer(), server_default='1'),
        sa.Column('content', sa.Text(), server_default=''),
        sa.Column('source', sa.String(30), server_default='ai'),
        sa.Column('editor_user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), index=True),
    )

    op.create_table(
        'member_timeline_reminders',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False, index=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('title', sa.String(200), server_default=''),
        sa.Column('body', sa.Text(), server_default=''),
        sa.Column('remind_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='1'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('member_timeline_reminders')
    op.drop_table('consultation_report_versions')
    op.drop_table('expert_consultations')
    op.drop_table('customer_vaults')
    op.drop_table('admission_schedules')
    op.drop_table('universities')
    op.drop_table('eligibility_records')
    op.drop_table('permission_configs')
    op.drop_table('recharge_codes')
    op.drop_table('payment_orders')
    op.drop_table('orders')
    op.drop_table('membership_plans')
    op.drop_table('auth_tokens')
    op.drop_table('users')
    op.drop_table('tenants')
