"""011 Admin Console V2 — staff profile fields.

Revision ID: 011_admin_console_v2
Revises: 010_student_crm_v1

Additive only. Feature/staging first. NO production apply in this PR.
- users.account_kind: CUSTOMER | STAFF (default CUSTOMER — never flip student owners)
- users.job_title
- users.last_login_at
- users.must_change_password
Backfill: existing role in staff set → STAFF; everyone else remains CUSTOMER.

Upgrade/downgrade are idempotent so a missing index cannot leave
alembic_version at 011 with columns already dropped (or vice versa).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "011_admin_console_v2"
down_revision = "010_student_crm_v1"
branch_labels = None
depends_on = None


def _user_columns() -> set[str]:
    bind = op.get_bind()
    return {c["name"] for c in sa.inspect(bind).get_columns("users")}


def _user_indexes() -> set[str]:
    bind = op.get_bind()
    return {i["name"] for i in sa.inspect(bind).get_indexes("users")}


def upgrade() -> None:
    cols = _user_columns()
    if "account_kind" not in cols:
        op.add_column("users", sa.Column("account_kind", sa.String(length=20), nullable=True))
    if "job_title" not in cols:
        op.add_column("users", sa.Column("job_title", sa.String(length=80), nullable=True))
    if "last_login_at" not in cols:
        op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))
    if "must_change_password" not in cols:
        op.add_column("users", sa.Column("must_change_password", sa.Boolean(), nullable=True))
    if "ix_users_account_kind" not in _user_indexes():
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
    if "ix_users_account_kind" in _user_indexes():
        op.drop_index("ix_users_account_kind", table_name="users")
    cols = _user_columns()
    for name in ("must_change_password", "last_login_at", "job_title", "account_kind"):
        if name in cols:
            op.drop_column("users", name)
