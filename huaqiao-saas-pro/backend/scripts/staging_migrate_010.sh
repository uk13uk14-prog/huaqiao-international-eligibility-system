#!/usr/bin/env bash
# Staging-only Alembic migrate for Student CRM V1 (010).
# NEVER point this at M1 production (127.0.0.1:5433/huaqiao).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STAGING_DATABASE_URL="${STAGING_DATABASE_URL:-postgresql+psycopg://guoqiao_staging:staging_local_only@127.0.0.1:5432/huaqiao_admin_staging}"

case "$STAGING_DATABASE_URL" in
  *5433*)
    echo "REFUSE: production port 5433" >&2
    exit 2
    ;;
esac
if [[ "$STAGING_DATABASE_URL" == *"/huaqiao" && "$STAGING_DATABASE_URL" != *"/huaqiao_admin_staging"* ]]; then
  echo "REFUSE: looks like production DB name huaqiao" >&2
  exit 2
fi

export DATABASE_URL="$STAGING_DATABASE_URL"
echo "STAGING_DATABASE_URL_REDACTED=$(echo "$DATABASE_URL" | sed -E 's#://([^:/]+):([^@]+)@#://\1:***@#')"
echo "PRODUCTION_DATABASE_TOUCHED=NO"

MODE="${1:-cycle}"
EXPECTED_BEFORE="009_csca_notification_rules"
EXPECTED_AFTER="010_student_crm_v1"

alembic_cmd() {
  python3 -m alembic "$@"
}

case "$MODE" in
  up)
    alembic_cmd upgrade "$EXPECTED_AFTER"
    alembic_cmd current
    ;;
  down)
    alembic_cmd downgrade "$EXPECTED_BEFORE"
    alembic_cmd current
    ;;
  reup|cycle)
    echo "== upgrade 010 =="
    alembic_cmd upgrade "$EXPECTED_AFTER"
    alembic_cmd current
    echo "== downgrade 009 =="
    alembic_cmd downgrade "$EXPECTED_BEFORE"
    alembic_cmd current
    echo "== re-upgrade 010 =="
    alembic_cmd upgrade "$EXPECTED_AFTER"
    alembic_cmd current
    ;;
  *)
    echo "usage: $0 [up|down|cycle]" >&2
    exit 1
    ;;
esac
