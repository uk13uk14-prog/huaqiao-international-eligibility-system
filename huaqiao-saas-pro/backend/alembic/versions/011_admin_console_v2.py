"""011 Admin Console V2 — staff profile fields.

Revision ID: 011_admin_console_v2
Revises: 010_student_crm_v1

Additive only. Feature/staging first. NO production apply in this PR.
- users.account_kind: CUSTOMER | STAFF (default CUSTOMER — never flip student owners)
- users.job_title
- users.last_login_at
- users.must_change_password
Backfill: existing role in staff set → STAFF; everyone else remains CUSTOMER.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "011_admin_console_v2"
down_revision = "010_student_crm_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("account_kind", sa.String(length=20), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=True))
    op.create_index("ix_users_account_kind", "users", ["account_kind"])
    op.execute("UPDATE users SET account_kind = 'CUSTOMER' WHERE account_kind IS NULL")
    op.execute(
        "UPDATE users SET account_kind = 'STAFF' "
        "WHERE lower(coalesce(role,'')) IN "
        "('admin','super_admin','operations_admin','consultant','support')"
    )
    op.execute("UPDATE users SET job_title = '' WHERE job_title IS NULL")
    op.execute("UPDATE users SET must_change_password = false WHERE must_change_password IS NULL")
    op.execute("UPDATE users SET job_title = '管理员' WHERE lower(coalesce(role,'')) = 'admin' AND coalesce(job_title,'') = ''")


def downgrade() -> None:
    op.drop_index("ix_users_account_kind", table_name="users")
    op.drop_column("users", "must_change_password")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "job_title")
    op.drop_column("users", "account_kind")
