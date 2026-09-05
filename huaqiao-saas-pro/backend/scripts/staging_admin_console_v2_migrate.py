#!/usr/bin/env python3
"""Staging-only Alembic cycle: 010 → 011 → 010 → 011.

Refuses production DB (port 5433 / bare /huaqiao).
Never writes to 127.0.0.1:5433/huaqiao.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

BACKEND = Path(__file__).resolve().parents[1]
STAGING_URL = os.environ.get(
    "STAGING_DATABASE_URL",
    "postgresql+psycopg://guoqiao_staging:staging_local_only@127.0.0.1:5432/huaqiao_admin_staging",
)
EXPECTED_BEFORE = "010_student_crm_v1"
EXPECTED_AFTER = "011_admin_console_v2"


def refuse_prod(url: str) -> None:
    if ":5433" in url:
        raise SystemExit("REFUSE: production port 5433")
    if url.rstrip("/").endswith("/huaqiao") or "/huaqiao?" in url:
        raise SystemExit("REFUSE: production database name huaqiao")


def cfg() -> Config:
    c = Config(str(BACKEND / "alembic.ini"))
    c.set_main_option("sqlalchemy.url", STAGING_URL.replace("%", "%%"))
    return c


def revision(eng) -> str:
    with eng.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar() or ""


def snap(eng) -> dict:
    q_tables = text(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name"
    )
    q_cols = text(
        "SELECT table_name||'.'||column_name FROM information_schema.columns "
        "WHERE table_schema='public' ORDER BY 1"
    )
    q_idx = text(
        "SELECT indexname FROM pg_indexes WHERE schemaname='public' ORDER BY indexname"
    )
    q_fk = text(
        "SELECT tc.constraint_name FROM information_schema.table_constraints tc "
        "WHERE tc.table_schema='public' AND tc.constraint_type='FOREIGN KEY' "
        "ORDER BY tc.constraint_name"
    )
    q_chk = text(
        "SELECT tc.constraint_name FROM information_schema.table_constraints tc "
        "WHERE tc.table_schema='public' AND tc.constraint_type='CHECK' "
        "ORDER BY tc.constraint_name"
    )
    q_enum = text("SELECT t.typname FROM pg_type t JOIN pg_enum e ON t.oid=e.enumtypid GROUP BY t.typname")
    with eng.connect() as conn:
        return {
            "tables": {r[0] for r in conn.execute(q_tables)},
            "columns": {r[0] for r in conn.execute(q_cols)},
            "indexes": {r[0] for r in conn.execute(q_idx)},
            "fks": {r[0] for r in conn.execute(q_fk)},
            "checks": {r[0] for r in conn.execute(q_chk)},
            "enums": {r[0] for r in conn.execute(q_enum)},
        }


def fmt(items: set[str]) -> str:
    return ",".join(sorted(items)) if items else "none"


def main() -> int:
    refuse_prod(STAGING_URL)
    os.chdir(BACKEND)
    eng = create_engine(STAGING_URL)
    before_rev = revision(eng)
    print(f"STAGING_DB=huaqiao_admin_staging@127.0.0.1:5432")
    print(f"STAGING_REVISION_BEFORE={before_rev}")
    if before_rev not in {EXPECTED_BEFORE, EXPECTED_AFTER}:
        print(f"UNEXPECTED_REVISION={before_rev}")
        return 2
    if before_rev == EXPECTED_AFTER:
        print("NOTE=already at 011; downgrade to 010 first so the cycle starts from 010")
        command.downgrade(cfg(), EXPECTED_BEFORE)
        before_rev = revision(eng)
        print(f"STAGING_REVISION_RESET={before_rev}")
    if before_rev != EXPECTED_BEFORE:
        print(f"REFUSE: expected {EXPECTED_BEFORE} before cycle, got {before_rev}")
        return 2

    pre = snap(eng)
    command.upgrade(cfg(), EXPECTED_AFTER)
    mid = revision(eng)
    upgrade_ok = mid == EXPECTED_AFTER
    print(f"STAGING_UPGRADE={'PASS' if upgrade_ok else 'FAIL:' + mid}")
    if not upgrade_ok:
        return 1

    post = snap(eng)
    print(f"TABLES_ADDED={fmt(post['tables'] - pre['tables'])}")
    print(f"COLUMNS_ADDED={fmt(post['columns'] - pre['columns'])}")
    print(f"INDEXES_ADDED={fmt(post['indexes'] - pre['indexes'])}")
    print(f"FOREIGN_KEYS_ADDED={fmt(post['fks'] - pre['fks'])}")
    print(f"ENUM_OR_CHECK_CONSTRAINTS={fmt((post['enums'] - pre['enums']) | (post['checks'] - pre['checks']))}")

    command.downgrade(cfg(), EXPECTED_BEFORE)
    down = revision(eng)
    down_ok = down == EXPECTED_BEFORE
    print(f"STAGING_DOWNGRADE={'PASS' if down_ok else 'FAIL:' + down}")
    if not down_ok:
        return 1
    after_down = snap(eng)
    leftover = after_down["columns"] - pre["columns"]
    if leftover:
        print(f"DOWNGRADE_LEFTOVER_COLUMNS={fmt(leftover)}")
        return 1

    command.upgrade(cfg(), EXPECTED_AFTER)
    after = revision(eng)
    re_ok = after == EXPECTED_AFTER
    print(f"STAGING_REUPGRADE={'PASS' if re_ok else 'FAIL:' + after}")
    print(f"STAGING_REVISION_AFTER={after}")
    print("PRODUCTION_DATABASE_TOUCHED=NO")
    return 0 if re_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
