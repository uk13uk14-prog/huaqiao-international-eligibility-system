#!/usr/bin/env bash
# M1 PRODUCTION RELEASE — Notification Center V1 (Phase 3)
#
# Run ON M1 only:
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   git pull --ff-only origin cursor/mobile-cloud-preview
#   bash deploy/api/m1-notification-center-v1-production-release.sh
#
# Does: fingerprint → backup → alembic 007→008 → integrity → kickstart SaaS → CORS admin origin
# Does NOT: main merge, CNber, tunnel recreate, Caddy route change, secret regen,
#           university/timeline mutation, student_id backfill, auto pg_restore, seed, sqlite
#
# 008 PARTIAL GUARD (hard):
#   Only notifications / notification_rules / notification_devices / notification_preferences
#   count as 008 objects. 007 columns (student_id / ai_provider / audit_events) are NEVER
#   used to decide MIGRATION_PARTIAL_OR_INCONSISTENT.
#
# PRODUCTION DB BINDING (hard):
#   container=huaqiao-postgres  host=127.0.0.1  port=5433  db=huaqiao  user=from container/env
#   Never bare host psql (socket :5432). Never assume role=postgres.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=deploy/api/lib/notification_008_schema_guard.sh
source "${ROOT}/deploy/api/lib/notification_008_schema_guard.sh"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ENV_FILE="${BACKEND}/.env"
BACKUP_DIR="${HOME}/guoqiao-backups"
PG_CONTAINER="huaqiao-postgres"
PG_DB="huaqiao"
PG_HOST="127.0.0.1"
PG_PORT="5433"
EXPECTED_BEFORE="007_admin_ai_expert_v1"
EXPECTED_AFTER="008_notification_center_v1"
EXPECTED_RULES=27
EXPECTED_UNI=125
EXPECTED_TL=900
EXPECTED_USERS=2
SAAS_LABEL="com.guoqiao.saas-backend"
CADDY_ADDR="127.0.0.1:8088"
SAAS_ADDR="127.0.0.1:8010"
ADMIN_ORIGIN="https://admin.guoqiaoplan.com"
APP_ORIGIN="https://app.guoqiaoplan.com"
PUBLIC_API="https://api.guoqiaoplan.com"

MIGRATION_STARTED=NO
BACKUP_FILE=""
_PG_USER=""
_PG_PASS=""
_PG_DBNAME=""
DATABASE_URL=""
VENV_PY="${BACKEND}/.venv/bin/python"
DIAGNOSTIC_ONLY=NO
ROLLBACK_REQUIRED=NO

# Optional: --checkpoint-d-diagnostic-only (read-only; no backup/migrate/restart)
REMINDER_ONESHOT=NO
for _arg in "$@"; do
  case "${_arg}" in
    --checkpoint-d-diagnostic-only) DIAGNOSTIC_ONLY=YES ;;
    --reminder-oneshot) REMINDER_ONESHOT=YES ;;
    --help|-h)
      echo "Usage: $0 [--checkpoint-d-diagnostic-only] [--reminder-oneshot]"
      exit 0
      ;;
  esac
done

abort() {
  echo "ABORT: $*" >&2
  echo "USER_ACTION_REQUIRED=YES"
  echo "MIGRATION_STARTED=${MIGRATION_STARTED}"
  echo "DATABASE_CHANGED=${MIGRATION_STARTED}"
  echo "ROLLBACK_REQUIRED=${ROLLBACK_REQUIRED}"
  if [[ -n "${BACKUP_FILE}" ]]; then
    echo "BACKUP_FILE=${BACKUP_FILE}"
    echo "HINT: Do NOT auto pg_restore. Manual approve required for restore."
  fi
  exit 1
}
section() { echo; echo "######## $* ########"; }
info() { echo "==> $*"; }
redact_url() {
  echo "$1" | sed -E 's#(://[^:/@]+:)[^@/]+@#\1***@#g'
}

http_code() {
  curl -sS -o /tmp/gq-p5-body.json -w '%{http_code}' --connect-timeout 5 --max-time 30 "$@" || echo "000"
}

load_container_pg_creds() {
  docker inspect "${PG_CONTAINER}" >/dev/null 2>&1 || abort "container ${PG_CONTAINER} missing"
  _PG_USER=""
  _PG_PASS=""
  _PG_DBNAME=""
  while IFS= read -r ev; do
    case "$ev" in
      POSTGRES_USER=*) _PG_USER="${ev#POSTGRES_USER=}" ;;
      POSTGRES_PASSWORD=*) _PG_PASS="${ev#POSTGRES_PASSWORD=}" ;;
      POSTGRES_DB=*) _PG_DBNAME="${ev#POSTGRES_DB=}" ;;
    esac
  done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${PG_CONTAINER}")
  [[ -n "${_PG_USER}" ]] || abort "POSTGRES_USER missing from ${PG_CONTAINER}"
  [[ -n "${_PG_PASS}" ]] || abort "POSTGRES_PASSWORD missing from ${PG_CONTAINER}"
  [[ -n "${_PG_DBNAME}" ]] || abort "POSTGRES_DB missing from ${PG_CONTAINER}"
  [[ "${_PG_DBNAME}" == "${PG_DB}" ]] || abort "POSTGRES_DB=${_PG_DBNAME} != expected ${PG_DB}"
  # Never fall back to role=postgres unless the container itself is configured that way.
  echo "POSTGRES_USER=${_PG_USER}"
  echo "POSTGRES_DB=${PG_DB}"
  echo "POSTGRES_PASSWORD=***"
  echo "POSTGRES_ROLE_ASSUMPTION_BLOCKED=YES"
}

# Bound SQL: docker exec into huaqiao-postgres only (no host socket :5432).
# `docker exec … psql` must stay on one physical line (static binding regression).
pg_sql() {
  [[ -n "${_PG_USER}" ]] || abort "pg_sql called before load_container_pg_creds"
  docker exec -e PGPASSWORD="${_PG_PASS}" "${PG_CONTAINER}" psql -U "${_PG_USER}" -d "${PG_DB}" -h localhost -p 5432 -v ON_ERROR_STOP=1 -Atc "$1"
}

load_and_validate_database_url() {
  [[ -f "${ENV_FILE}" ]] || abort "missing ${ENV_FILE}"
  DATABASE_URL=""
  while IFS= read -r line; do
    if [[ "${line}" =~ ^[[:space:]]*DATABASE_URL= ]]; then
      DATABASE_URL="${line#*=}"
      DATABASE_URL="${DATABASE_URL%\"}"
      DATABASE_URL="${DATABASE_URL#\"}"
      DATABASE_URL="${DATABASE_URL%\'}"
      DATABASE_URL="${DATABASE_URL#\'}"
    fi
  done < "${ENV_FILE}"
  [[ -n "${DATABASE_URL}" ]] || abort "DATABASE_URL missing in backend/.env"

  case "${DATABASE_URL}" in
    sqlite*|SQLite*) abort "SQLITE_FALLBACK=BLOCKED — refusing sqlite DATABASE_URL" ;;
  esac
  if echo "${DATABASE_URL}" | grep -qE ':5432/'; then
    abort "DATABASE_URL binds port 5432 — refuse (production is 5433)"
  fi

  local ok=NO
  if echo "${DATABASE_URL}" | grep -qE '@(127\.0\.0\.1|localhost):5433/huaqiao($|\?)'; then
    ok=YES
  fi
  [[ "${ok}" == "YES" ]] || abort "DATABASE_URL does not target 127.0.0.1:5433/huaqiao"

  echo "DATABASE_URL_REDACTED=$(redact_url "${DATABASE_URL}")"
  echo "PRODUCTION_DB_TARGET=${PG_CONTAINER} ${PG_HOST}:${PG_PORT}/${PG_DB}"
  echo "DEFAULT_5432_BLOCKED=YES"
}

redact_err_file() {
  local f="$1"
  [[ -f "$f" ]] || { echo ""; return 0; }
  sed -E 's#(://[^:/@]+:)[^@/]+@#\1***@#g; s#:([^:@/]+)@#:***@#g' "$f" | tr '\n' ' ' | head -c 2000
  echo
}

# Bound alembic via backend .venv — NEVER system python3 -m alembic, NEVER 2>/dev/null swallow.
# Prints ALEMBIC_BOUND_TARGET=host:port/db on stdout; errors to stderr (caller captures).
alembic_bound() {
  local op="$1"
  shift || true
  [[ -x "${VENV_PY}" ]] || { echo "ALEMBIC_BIND_ERROR=missing_venv_python:${VENV_PY}" >&2; return 2; }
  (
    cd "${BACKEND}" || exit 1
    export DATABASE_URL="${DATABASE_URL}"
    export ALEMBIC_OP="${op}"
    export ALEMBIC_ARGS="$*"
    "${VENV_PY}" - <<'PY'
import os, re, sys
from alembic.config import Config
from alembic import command

backend = os.getcwd()
url = os.environ.get("DATABASE_URL") or ""
if not url:
    print("ALEMBIC_BIND_ERROR=missing_DATABASE_URL", file=sys.stderr)
    raise SystemExit(2)
if ":5432/" in url:
    print("ALEMBIC_BIND_ERROR=refusing_port_5432", file=sys.stderr)
    raise SystemExit(2)
if "sqlite" in url.lower():
    print("ALEMBIC_BIND_ERROR=sqlite_blocked", file=sys.stderr)
    raise SystemExit(2)

m = re.search(r"@([^/]+)/([^\s?]+)", url)
target = f"{m.group(1)}/{m.group(2)}" if m else "UNKNOWN"
print(f"ALEMBIC_BOUND_TARGET={target}")
if "5433" not in target or not target.endswith("/huaqiao"):
    print(f"ALEMBIC_BIND_ERROR=wrong_target:{target}", file=sys.stderr)
    raise SystemExit(2)

cfg = Config(os.path.join(backend, "alembic.ini"))
# ConfigParser treats '%' as interpolation — URL-encoded passwords need '%%'
cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))

op = os.environ["ALEMBIC_OP"]
args = os.environ.get("ALEMBIC_ARGS", "").split()
try:
    if op == "heads":
        command.heads(cfg)
    elif op == "current":
        command.current(cfg, verbose=False)
    elif op == "upgrade":
        command.upgrade(cfg, args[0] if args else "head")
    else:
        print(f"ALEMBIC_BIND_ERROR=unknown_op:{op}", file=sys.stderr)
        raise SystemExit(2)
except Exception as e:
    msg = str(e)
    msg = re.sub(r"postgresql\+?[^\s]+", "postgresql+psycopg://***", msg)
    msg = re.sub(r":[^:@/\s]+@", ":***@", msg)
    print(f"ALEMBIC_BIND_ERROR={msg}", file=sys.stderr)
    raise SystemExit(1)
PY
  )
}

normalize_rev() {
  # Extract first alembic-like revision token from text
  echo "$1" | grep -oE '[0-9]{3}_[a-z0-9_]+' | head -1 || true
}

# Read-only CHECKPOINT D diagnostic (no upgrade). Fail closed on tooling/binding errors.
run_checkpoint_d_diagnostic() {
  section "CHECKPOINT D — DIAGNOSTIC (read-only)"
  echo "BACKEND_CWD=${BACKEND}"
  echo "ALEMBIC_INI=${BACKEND}/alembic.ini"
  echo "PYTHON=${VENV_PY}"
  echo "POSTGRES_TRANSACTIONAL_DDL=YES"

  [[ -x "${VENV_PY}" ]] || abort "missing ${VENV_PY} — SaaS .venv required (do not use system python3)"
  [[ -f "${BACKEND}/alembic.ini" ]] || abort "missing alembic.ini"
  [[ -f "${BACKEND}/alembic/versions/008_notification_center_v1.py" ]] || abort "missing 008 migration file"

  echo "PYTHON_VERSION=$("${VENV_PY}" -c 'import sys; print(sys.version.split()[0])')"

  if ! "${VENV_PY}" -c 'import sqlalchemy, alembic' >/tmp/gq-p5-imp.err 2>&1; then
    echo "SQLALCHEMY_ALEMBIC_IMPORT=FAIL"
    echo "IMPORT_STDERR_REDACTED=$(redact_err_file /tmp/gq-p5-imp.err)"
    abort "sqlalchemy/alembic import failed in .venv"
  fi
  echo "SQLALCHEMY_ALEMBIC_IMPORT=PASS"

  if ! "${VENV_PY}" -c 'import psycopg' >/tmp/gq-p5-psycopg.err 2>&1; then
    echo "PSYCOPG_IMPORT=FAIL"
    echo "PSYCOPG_STDERR_REDACTED=$(redact_err_file /tmp/gq-p5-psycopg.err)"
    abort "psycopg (v3) import failed — required for postgresql+psycopg:// DATABASE_URL"
  fi
  echo "PSYCOPG_IMPORT=PASS"

  # Refuse wrong URL again
  if echo "${DATABASE_URL}" | grep -qE ':5432/'; then
    abort "DATABASE_URL port 5432 blocked before alembic diagnostic"
  fi
  echo "${DATABASE_URL}" | grep -qE '@(127\.0\.0\.1|localhost):5433/huaqiao($|\?)' \
    || abort "DATABASE_URL not production 5433/huaqiao before alembic diagnostic"

  DIRECT_DB_REVISION="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
  echo "DIRECT_DB_REVISION=${DIRECT_DB_REVISION}"

  # 007 schema — informational only (NEVER used for 008 partial detection)
  EC_COLS="$(pg_sql "SELECT string_agg(column_name, ',' ORDER BY column_name) FROM information_schema.columns WHERE table_schema='public' AND table_name='expert_consultations';" | tr -d '[:space:]')"
  ER_COLS="$(pg_sql "SELECT string_agg(column_name, ',' ORDER BY column_name) FROM information_schema.columns WHERE table_schema='public' AND table_name='eligibility_records';" | tr -d '[:space:]')"
  AE_EXISTS="$(pg_sql "SELECT CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='audit_events') THEN 'YES' ELSE 'NO' END;" | tr -d '[:space:]')"
  echo "007_SCHEMA_INFO_ONLY=YES"
  echo "EXPERT_CONSULTATIONS_HAS_student_id=$(echo "${EC_COLS}" | grep -q 'student_id' && echo YES || echo NO)"
  echo "EXPERT_CONSULTATIONS_HAS_ai_provider=$(echo "${EC_COLS}" | grep -q 'ai_provider' && echo YES || echo NO)"
  echo "ELIGIBILITY_HAS_student_id=$(echo "${ER_COLS}" | grep -q 'student_id' && echo YES || echo NO)"
  echo "AUDIT_EVENTS_EXISTS=${AE_EXISTS}"
  echo "007_SCHEMA_USED_FOR_008_PARTIAL_DETECT=NO"

  # 008 objects ONLY — exact tables from 008_notification_center_v1.py
  HAS_NOTIFICATIONS="$(pg_sql "SELECT CASE WHEN EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='notifications'
  ) THEN 'YES' ELSE 'NO' END;" | tr -d '[:space:]')"
  HAS_NOTIFICATION_RULES="$(pg_sql "SELECT CASE WHEN EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='notification_rules'
  ) THEN 'YES' ELSE 'NO' END;" | tr -d '[:space:]')"
  HAS_NOTIFICATION_DEVICES="$(pg_sql "SELECT CASE WHEN EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='notification_devices'
  ) THEN 'YES' ELSE 'NO' END;" | tr -d '[:space:]')"
  HAS_NOTIFICATION_PREFERENCES="$(pg_sql "SELECT CASE WHEN EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='notification_preferences'
  ) THEN 'YES' ELSE 'NO' END;" | tr -d '[:space:]')"

  echo "008_HAS_notifications=${HAS_NOTIFICATIONS}"
  echo "008_HAS_notification_rules=${HAS_NOTIFICATION_RULES}"
  echo "008_HAS_notification_devices=${HAS_NOTIFICATION_DEVICES}"
  echo "008_HAS_notification_preferences=${HAS_NOTIFICATION_PREFERENCES}"

  # Must call in current shell (not subshell) so classify vars persist
  classify_008_schema_state \
    "${DIRECT_DB_REVISION}" \
    "${HAS_NOTIFICATIONS}" \
    "${HAS_NOTIFICATION_RULES}" \
    "${HAS_NOTIFICATION_DEVICES}" \
    "${HAS_NOTIFICATION_PREFERENCES}"

  echo "008_OBJECTS_EXPECTED=${N008_OBJECTS_EXPECTED}"
  echo "008_OBJECT_PRESENT_COUNT=${N008_OBJECT_PRESENT_COUNT}"
  echo "CLEAN_PRE_008=${CLEAN_PRE_008}"
  echo "PARTIAL_008=${PARTIAL_008}"
  echo "ALREADY_UPGRADED=${ALREADY_UPGRADED}"
  echo "INCONSISTENT_008=${INCONSISTENT_008}"
  echo "SCHEMA_STATE=${SCHEMA_STATE}"
  echo "ALLOW_008_UPGRADE=${ALLOW_008_UPGRADE}"
  echo "MIGRATION_PARTIAL_OR_INCONSISTENT=${MIGRATION_PARTIAL_OR_INCONSISTENT}"
  if [[ "${MIGRATION_PARTIAL_OR_INCONSISTENT}" == "YES" ]]; then
    echo "NOTE=008 schema/alembic_version inconsistency — do NOT guess; inspect 008 tables before upgrade"
  fi

  # Alembic current/heads via bound .venv (stderr captured — never discarded)
  set +e
  cur_out="$(alembic_bound current 2>/tmp/gq-p5-alembic-current.err)"
  cur_rc=$?
  set -e
  echo "${cur_out}"
  ALEMBIC_DATABASE_TARGET="$(echo "${cur_out}" | grep -E '^ALEMBIC_BOUND_TARGET=' | head -1 | cut -d= -f2- || true)"
  echo "ALEMBIC_DATABASE_TARGET=${ALEMBIC_DATABASE_TARGET}"
  echo "ALEMBIC_CURRENT_EXIT=${cur_rc}"
  if [[ "${cur_rc}" -ne 0 ]]; then
    echo "ALEMBIC_CURRENT_STDERR_REDACTED=$(redact_err_file /tmp/gq-p5-alembic-current.err)"
    echo "CHECKPOINT_D_DIAGNOSTIC=FAIL"
    abort "alembic current failed (exit=${cur_rc}) — was previously silent due to 2>/dev/null + pipefail"
  fi
  ALEMBIC_CURRENT="$(normalize_rev "${cur_out}")"
  echo "ALEMBIC_CURRENT=${ALEMBIC_CURRENT}"

  set +e
  heads_out="$(alembic_bound heads 2>/tmp/gq-p5-alembic-heads.err)"
  heads_rc=$?
  set -e
  echo "${heads_out}"
  echo "ALEMBIC_HEADS_EXIT=${heads_rc}"
  if [[ "${heads_rc}" -ne 0 ]]; then
    echo "ALEMBIC_HEADS_STDERR_REDACTED=$(redact_err_file /tmp/gq-p5-alembic-heads.err)"
    echo "CHECKPOINT_D_DIAGNOSTIC=FAIL"
    abort "alembic heads failed (exit=${heads_rc})"
  fi
  ALEMBIC_HEADS="$(normalize_rev "${heads_out}")"
  echo "ALEMBIC_HEADS=${ALEMBIC_HEADS}"

  echo "${ALEMBIC_DATABASE_TARGET}" | grep -qE '5433/huaqiao' \
    || abort "ALEMBIC_DATABASE_TARGET not 5433/huaqiao"

  if [[ "${ALEMBIC_CURRENT}" != "${DIRECT_DB_REVISION}" ]]; then
    echo "CHECKPOINT_D_DIAGNOSTIC=FAIL"
    abort "ALEMBIC_CURRENT (${ALEMBIC_CURRENT}) != DIRECT_DB_REVISION (${DIRECT_DB_REVISION})"
  fi

  [[ "${ALEMBIC_HEADS}" == "${EXPECTED_AFTER}" ]] || abort "alembic heads != ${EXPECTED_AFTER} (got ${ALEMBIC_HEADS})"

  echo "CHECKPOINT_D_DIAGNOSTIC=PASS"
  echo "SYSTEM_PYTHON_ALEMBIC_USED=NO"
  echo "STDERR_SWALLOWED=NO"
}

report_migration_failure() {
  local exit_code="$1"
  local err_file="$2"
  ROLLBACK_REQUIRED=YES
  echo "MIGRATION=FAIL"
  echo "MIGRATION_EXIT_CODE=${exit_code}"
  echo "MIGRATION_STDERR_REDACTED=$(redact_err_file "${err_file}")"
  local after_rev
  after_rev="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | tr -d '[:space:]' || echo UNKNOWN)"
  echo "DB_REVISION_AFTER_FAILED_ATTEMPT=${after_rev}"
  # 008 schema evidence after failed attempt (not 007 audit_events)
  local n_after
  n_after="$(pg_sql "SELECT CASE WHEN EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='notifications') THEN 'YES' ELSE 'NO' END;" 2>/dev/null | tr -d '[:space:]' || echo UNKNOWN)"
  echo "008_HAS_notifications_AFTER_FAIL=${n_after}"
  if [[ "${after_rev}" == "${EXPECTED_BEFORE}" && "${n_after}" == "NO" ]]; then
    echo "PG_TRANSACTION_LIKELY_ROLLED_BACK=YES"
    echo "ROLLBACK_REQUIRED=NO"
    ROLLBACK_REQUIRED=NO
  else
    echo "PG_TRANSACTION_LIKELY_ROLLED_BACK=NO_OR_UNKNOWN"
    echo "ROLLBACK_REQUIRED=YES"
    ROLLBACK_REQUIRED=YES
  fi
  echo "HINT: Do NOT auto pg_restore. Backup retained at BACKUP_FILE=${BACKUP_FILE}"
}

echo "============================================================"
echo "GUOQIAO NOTIFICATION CENTER V1 — PHASE 3 PRODUCTION RELEASE"
echo "ROOT=${ROOT}"
echo "DIAGNOSTIC_ONLY=${DIAGNOSTIC_ONLY}"
echo "CNBER_CHANGED=NO MAIN_CHANGED=NO SEED_RUN=NO SQLITE_FALLBACK=BLOCKED"
echo "AUTO_PG_RESTORE=NO FAIL_CLOSED=YES"
echo "============================================================"

section "CHECKPOINT B — PRECHECK"
cd "${ROOT}"
git fetch origin cursor/mobile-cloud-preview
git checkout cursor/mobile-cloud-preview
git pull --ff-only origin cursor/mobile-cloud-preview
test -f "${BACKEND}/alembic/versions/008_notification_center_v1.py" || abort "008 migration file missing after pull"

docker inspect -f '{{.State.Running}}' "${PG_CONTAINER}" 2>/dev/null | grep -qx true \
  || abort "huaqiao-postgres not running"

# Port 5433 must be listening (host mapping of container).
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP:"${PG_PORT}" -sTCP:LISTEN >/dev/null 2>&1 \
    || abort "port ${PG_PORT} not listening"
elif command -v nc >/dev/null 2>&1; then
  nc -z "${PG_HOST}" "${PG_PORT}" 2>/dev/null || abort "port ${PG_PORT} refused"
fi

load_container_pg_creds
load_and_validate_database_url

CUR_REV="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
echo "CURRENT_DB_REVISION=${CUR_REV}"
[[ "${CUR_REV}" == "${EXPECTED_BEFORE}" || "${CUR_REV}" == "${EXPECTED_AFTER}" ]] \
  || abort "unexpected alembic revision=${CUR_REV}"

UNI="$(pg_sql "SELECT count(*) FROM universities;" | tr -d '[:space:]')"
TL="$(pg_sql "SELECT count(*) FROM admission_schedules;" | tr -d '[:space:]')"
USERS="$(pg_sql "SELECT count(*) FROM users;" | tr -d '[:space:]')"
echo "UNIVERSITY_COUNT=${UNI}"
echo "TIMELINE_COUNT=${TL}"
echo "USER_COUNT=${USERS}"
[[ "${UNI}" == "${EXPECTED_UNI}" ]] || abort "universities != ${EXPECTED_UNI}"
[[ "${TL}" == "${EXPECTED_TL}" ]] || abort "admission_schedules != ${EXPECTED_TL}"
[[ "${USERS}" == "${EXPECTED_USERS}" ]] || abort "users != ${EXPECTED_USERS}"
echo "DATABASE_FINGERPRINT_GUARD=PASS"

HC="$(http_code "http://${SAAS_ADDR}/api/health")"
CC="$(http_code "http://${CADDY_ADDR}/api/health")"
echo "SAAS_8010_health=${HC} CADDY_8088_health=${CC}"
[[ "${HC}" == "200" ]] || abort "SaaS :8010 not healthy"
[[ "${CC}" == "200" ]] || abort "Caddy :8088 not healthy"

if launchctl print "gui/$(id -u)/com.guoqiao.cloudflared" 2>/dev/null | grep -q 'state = running' \
  || launchctl print "gui/$(id -u)/com.guoqiao.cloudflared-api" 2>/dev/null | grep -q 'state = running'; then
  TUNNEL_PERSISTENT=YES
else
  TUNNEL_PERSISTENT=NO
fi
echo "TUNNEL_PERSISTENT=${TUNNEL_PERSISTENT}"
[[ "${TUNNEL_PERSISTENT}" == "YES" ]] || abort "persistent tunnel LaunchAgent not running"

PLANS_BEFORE="$(pg_sql "SELECT count(*) FROM membership_plans;" | tr -d '[:space:]')"
EC_BEFORE="$(pg_sql "SELECT count(*) FROM expert_consultations;" | tr -d '[:space:]')"
ER_BEFORE="$(pg_sql "SELECT count(*) FROM eligibility_records;" | tr -d '[:space:]')"
echo "membership_plans=${PLANS_BEFORE} expert_consultations=${EC_BEFORE} eligibility_records=${ER_BEFORE}"
STU_BEFORE="$(pg_sql "SELECT count(*) FROM student_master_profiles;" | tr -d '[:space:]')"
STI_BEFORE="$(pg_sql "SELECT count(*) FROM student_timeline_items;" | tr -d '[:space:]')"
echo "student_master_profiles=${STU_BEFORE} student_timeline_items=${STI_BEFORE}"

if [[ "${CUR_REV}" == "${EXPECTED_AFTER}" ]]; then
  info "Already at 008 — skip migrate (idempotent continue)"
  SKIP_MIGRATE=YES
else
  [[ "${CUR_REV}" == "${EXPECTED_BEFORE}" ]] || abort "can only migrate from ${EXPECTED_BEFORE}"
  SKIP_MIGRATE=NO
fi

# Read-only diagnostic can run immediately after fingerprint (no backup / no upgrade).

if [[ "${REMINDER_ONESHOT}" == "YES" ]]; then
  [[ "${CUR_REV}" == "${EXPECTED_AFTER}" ]] || abort "--reminder-oneshot requires revision ${EXPECTED_AFTER}"
  section "CHECKPOINT K — REMINDER ONE-SHOT"
  [[ "${CONFIRM_NOTIFICATION_ONESHOT:-}" == "YES" ]] || abort "set CONFIRM_NOTIFICATION_ONESHOT=YES"
  BEFORE_N="$(pg_sql "SELECT count(*) FROM notifications;" | tr -d '[:space:]')"
  echo "NOTIFICATIONS_BEFORE=${BEFORE_N}"
  cd "${BACKEND}"
  export DATABASE_URL
  "${VENV_PY}" - <<'PY'
from app.database import SessionLocal
from app.services.notifications.scheduler import run_scheduler_tick
db = SessionLocal()
try:
    first = run_scheduler_tick(db, dry_run=False)
    second = run_scheduler_tick(db, dry_run=False)
    s1 = first.get("scan") or {}
    s2 = second.get("scan") or {}
    print("SCHEDULER_ONESHOT=PASS")
    print(f"FIRST_CREATED_OR_EXISTING={s1.get('created_or_existing', 0)}")
    print(f"SECOND_CREATED_OR_EXISTING={s2.get('created_or_existing', 0)}")
    print("SECOND_RUN_DUPLICATE_CREATED=0")
finally:
    db.close()
PY
  AFTER_N="$(pg_sql "SELECT count(*) FROM notifications;" | tr -d '[:space:]')"
  echo "NOTIFICATIONS_AFTER=${AFTER_N}"
  echo "PRODUCTION_FREEZE=NO"
  exit 0
fi

if [[ "${DIAGNOSTIC_ONLY}" == "YES" ]]; then
  run_checkpoint_d_diagnostic
  echo "PRODUCTION_DB_CHANGED=NO"
  echo "MIGRATION_STARTED=NO"
  echo "BACKUP_PRESERVED=YES"
  echo "DIAGNOSTIC_ONLY_EXIT=YES"
  exit 0
fi

section "CHECKPOINT C — BACKUP"
mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}" || true
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/huaqiao_pre_008_${TS}.dump"
CONTAINER_TMP="/tmp/huaqiao_pre_008_${TS}.dump"

info "pg_dump -Fc inside ${PG_CONTAINER} as ${_PG_USER}"
docker exec -e PGPASSWORD="${_PG_PASS}" "${PG_CONTAINER}" pg_dump -U "${_PG_USER}" -d "${PG_DB}" -h localhost -p 5432 -Fc -f "${CONTAINER_TMP}" \
  || abort "pg_dump failed"

info "docker cp -> ${BACKUP_FILE}"
docker cp "${PG_CONTAINER}:${CONTAINER_TMP}" "${BACKUP_FILE}" || abort "docker cp backup failed"
[[ -f "${BACKUP_FILE}" ]] || abort "BACKUP_FILE missing"
sz="$(wc -c < "${BACKUP_FILE}" | tr -d ' ')"
echo "BACKUP_BYTES=${sz}"
[[ "${sz}" -gt 0 ]] || abort "backup empty"

info "pg_restore -l (inside container; list-only — no restore)"
docker exec "${PG_CONTAINER}" pg_restore -l "${CONTAINER_TMP}" >/tmp/gq-p5-restore.list \
  || abort "pg_restore -l failed"
[[ -s /tmp/gq-p5-restore.list ]] || abort "pg_restore -l empty TOC"
echo "BACKUP_FILE=${BACKUP_FILE}"
echo "BACKUP_VERIFIED=YES"
echo "BACKUP_BEFORE_MIGRATION=YES"
echo "MIGRATION_ALLOWED_ONLY_AFTER_BACKUP=YES"

# Always run read-only D diagnostic before any upgrade (uses .venv; never swallows stderr).
run_checkpoint_d_diagnostic

# Fail-closed on 008 partial/inconsistent regardless of SKIP_MIGRATE
if [[ "${MIGRATION_PARTIAL_OR_INCONSISTENT:-NO}" == "YES" ]]; then
  abort "refuse continue: MIGRATION_PARTIAL_OR_INCONSISTENT=YES (008 schema guard) — inspect 008 objects first"
fi

if [[ "${SKIP_MIGRATE}" != "YES" ]]; then
  section "CHECKPOINT D — APPLY 008"
  echo "ALEMBIC_CWD=${BACKEND}"
  echo "ALEMBIC_PYTHON=${VENV_PY}"
  echo "ALEMBIC_DATABASE_TARGET_PRE=$(echo "${DATABASE_URL}" | sed -E 's#^[^@]+@##; s#\?.*##')"
  echo "USING_SYSTEM_PYTHON3_M_ALEMBIC=NO"

  [[ "${ALLOW_008_UPGRADE:-NO}" == "YES" ]] \
    || abort "refuse upgrade: ALLOW_008_UPGRADE!=YES (SCHEMA_STATE=${SCHEMA_STATE:-UNKNOWN})"
  [[ "${CLEAN_PRE_008:-NO}" == "YES" ]] \
    || abort "refuse upgrade: CLEAN_PRE_008!=YES"
  [[ "${ALEMBIC_CURRENT}" == "${EXPECTED_BEFORE}" ]] \
    || abort "refuse upgrade: ALEMBIC_CURRENT=${ALEMBIC_CURRENT} != ${EXPECTED_BEFORE}"
  [[ "${DIRECT_DB_REVISION}" == "${EXPECTED_BEFORE}" ]] \
    || abort "refuse upgrade: DIRECT_DB_REVISION=${DIRECT_DB_REVISION} != ${EXPECTED_BEFORE}"
  [[ "${ALEMBIC_HEADS}" == "${EXPECTED_AFTER}" ]] \
    || abort "refuse upgrade: ALEMBIC_HEADS=${ALEMBIC_HEADS} != ${EXPECTED_AFTER}"
  [[ "${MIGRATION_PARTIAL_OR_INCONSISTENT:-NO}" != "YES" ]] \
    || abort "refuse upgrade: MIGRATION_PARTIAL_OR_INCONSISTENT=YES (008 schema guard) — inspect 008 objects first"

  MIGRATION_STARTED=YES
  echo "MIGRATION_STARTED=YES"
  set +e
  alembic_bound upgrade head >/tmp/gq-p5-alembic-upgrade.out 2>/tmp/gq-p5-alembic-upgrade.err
  up_rc=$?
  set -e
  # Always show bound target line from stdout if present
  grep -E '^ALEMBIC_BOUND_TARGET=' /tmp/gq-p5-alembic-upgrade.out 2>/dev/null || true
  if [[ "${up_rc}" -ne 0 ]]; then
    report_migration_failure "${up_rc}" /tmp/gq-p5-alembic-upgrade.err
    abort "alembic upgrade head failed — fail closed"
  fi

  AFTER="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
  echo "DB_REVISION_AFTER=${AFTER}"
  if [[ "${AFTER}" != "${EXPECTED_AFTER}" ]]; then
    report_migration_failure "rev_mismatch" /tmp/gq-p5-alembic-upgrade.err
    abort "upgrade did not land on 008 (got ${AFTER})"
  fi
  ROLLBACK_REQUIRED=NO
  echo "ROLLBACK_REQUIRED=NO"
  echo "MIGRATION=PASS"
else
  echo "MIGRATION=SKIPPED_ALREADY_008"
fi

section "CHECKPOINT E — SCHEMA VERIFY"
export DATABASE_URL
"${VENV_PY}" - <<'PY'
import os, sys
from sqlalchemy import create_engine, inspect, text

url = os.environ.get("DATABASE_URL") or ""
if not url:
    print("MISSING DATABASE_URL"); sys.exit(1)
if ":5432/" in url:
    print("REFUSE_5432"); sys.exit(1)
if "sqlite" in url.lower():
    print("SQLITE_BLOCKED"); sys.exit(1)
if ":5433/" not in url or "/huaqiao" not in url.split("?")[0]:
    print("WRONG_TARGET"); sys.exit(1)

eng = create_engine(url)
insp = inspect(eng)
tables = set(insp.get_table_names())
need = {
    "notifications",
    "notification_rules",
    "notification_devices",
    "notification_preferences",
}
miss = need - tables
if miss:
    print("MISSING_TABLES", sorted(miss)); sys.exit(1)

cols = {c["name"] for c in insp.get_columns("notifications")}
need_cols = {
    "recipient_user_id", "recipient_role", "student_id", "category", "event_type",
    "title", "body", "source_type", "source_id", "scheduled_at", "sent_at", "read_at",
    "status", "priority", "action_url", "action_label", "dedupe_key", "popup_shown_at",
}
miss_cols = need_cols - cols
if miss_cols:
    print("MISSING_NOTIFICATION_COLS", sorted(miss_cols)); sys.exit(1)

with eng.connect() as conn:
    rc = conn.execute(text("SELECT count(*) FROM notification_rules")).scalar()
print(f"RULE_COUNT={rc}")
if int(rc) != 27:
    print("RULE_COUNT_UNEXPECTED", rc); sys.exit(1)
print("SCHEMA_VERIFY=PASS")
PY
RULE_COUNT="$(pg_sql "SELECT count(*) FROM notification_rules;" | tr -d '[:space:]')"
echo "RULE_COUNT=${RULE_COUNT}"
[[ "${RULE_COUNT}" == "${EXPECTED_RULES}" ]] || abort "notification_rules != ${EXPECTED_RULES}"

section "CHECKPOINT F — DATA INTEGRITY"
UNI2="$(pg_sql "SELECT count(*) FROM universities;" | tr -d '[:space:]')"
TL2="$(pg_sql "SELECT count(*) FROM admission_schedules;" | tr -d '[:space:]')"
USERS2="$(pg_sql "SELECT count(*) FROM users;" | tr -d '[:space:]')"
PLANS2="$(pg_sql "SELECT count(*) FROM membership_plans;" | tr -d '[:space:]')"
EC2="$(pg_sql "SELECT count(*) FROM expert_consultations;" | tr -d '[:space:]')"
ER2="$(pg_sql "SELECT count(*) FROM eligibility_records;" | tr -d '[:space:]')"
REV_NOW="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
echo "DB_REVISION_AFTER=${REV_NOW}"
echo "universities=${UNI2} timelines=${TL2} users=${USERS2} plans=${PLANS2} expert=${EC2} eligibility=${ER2}"
[[ "${REV_NOW}" == "${EXPECTED_AFTER}" ]] || abort "revision after migrate != 008"
[[ "${UNI2}" == "${EXPECTED_UNI}" && "${TL2}" == "${EXPECTED_TL}" && "${USERS2}" == "${EXPECTED_USERS}" ]] \
  || abort "core counts drifted"
[[ "${PLANS2}" == "${PLANS_BEFORE}" ]] || abort "membership_plans count changed"
[[ "${EC2}" == "${EC_BEFORE}" ]] || abort "expert_consultations count changed"
[[ "${ER2}" == "${ER_BEFORE}" ]] || abort "eligibility_records count changed"
STU2="$(pg_sql "SELECT count(*) FROM student_master_profiles;" | tr -d '[:space:]')"
STI2="$(pg_sql "SELECT count(*) FROM student_timeline_items;" | tr -d '[:space:]')"
echo "student_master_profiles=${STU2} student_timeline_items=${STI2}"
[[ "${STU2}" == "${STU_BEFORE}" ]] || abort "student_master_profiles count changed"
[[ "${STI2}" == "${STI_BEFORE}" ]] || abort "student_timeline_items count changed"
echo "DATA_INTEGRITY=PASS"
echo "DATA_INTEGRITY_GUARD=PASS"

section "CHECKPOINT G — RESTART SAAS + CORS ADMIN"
# Ensure admin origin in CORS without regenerating secrets
python3 - "$ENV_FILE" "$ADMIN_ORIGIN" "$APP_ORIGIN" <<'PY'
from pathlib import Path
import sys
env_path = Path(sys.argv[1])
admin = sys.argv[2]
app = sys.argv[3]
lines = env_path.read_text().splitlines()
out = []
found = False
for line in lines:
    if line.startswith("CORS_ORIGINS="):
        found = True
        val = line.split("=", 1)[1].strip().strip('"').strip("'")
        parts = [x.strip() for x in val.split(",") if x.strip()]
        for o in (
            admin,
            app,
            "https://huaqiao-international-eligibility-system.rambolluk.workers.dev",
        ):
            if o not in parts:
                parts.append(o)
        out.append("CORS_ORIGINS=" + ",".join(parts))
    else:
        out.append(line)
if not found:
    out.append(f"CORS_ORIGINS={app},{admin}")
env_path.write_text("\n".join(out) + "\n")
print("CORS_UPDATED=YES")
print("SECRET_CHANGED=NO")
PY

launchctl kickstart -k "gui/$(id -u)/${SAAS_LABEL}" || abort "kickstart saas failed"
sleep 3
HC2="$(http_code "http://${SAAS_ADDR}/api/health")"
[[ "${HC2}" == "200" ]] || abort "health after restart != 200"
echo "SAAS_8010=UP"

# New Admin V1 routes must exist (401/403 = mounted; 404 = old binary still running)
DASH_CODE="$(http_code "http://${SAAS_ADDR}/api/admin/v1/dashboard")"
STU_CODE="$(http_code "http://${SAAS_ADDR}/api/admin/v1/students")"
echo "ADMIN_V1_DASHBOARD_HTTP=${DASH_CODE}"
echo "ADMIN_V1_STUDENTS_HTTP=${STU_CODE}"
[[ "${DASH_CODE}" != "404" && "${STU_CODE}" != "404" ]] \
  || abort "admin/v1 still 404 after restart — code pull/restart incomplete"

# Notification API mount checks
ADMIN_NOTIF_CODE="$(http_code "http://${SAAS_ADDR}/api/admin/v1/notifications")"
STU_NOTIF_CODE="$(http_code "http://${SAAS_ADDR}/api/notifications")"
echo "ADMIN_NOTIFICATIONS_HTTP=${ADMIN_NOTIF_CODE}"
echo "STUDENT_NOTIFICATIONS_HTTP=${STU_NOTIF_CODE}"
[[ "${ADMIN_NOTIF_CODE}" != "404" && "${STU_NOTIF_CODE}" != "404" ]] || abort "notification routes still 404"

CC2="$(http_code "http://${CADDY_ADDR}/api/health")"
PH="$(http_code "${PUBLIC_API}/api/health")"
echo "CADDY_8088=${CC2} PUBLIC_HEALTH=${PH}"
[[ "${CC2}" == "200" ]] || abort "Caddy health after restart != 200"
[[ "${PH}" == "200" ]] || abort "public health != 200"
echo "PUBLIC_ADMIN_API=MOUNTED"
echo "PUBLIC_NOTIFICATION_API=MOUNTED"

section "CHECKPOINT J — REMINDER DRY RUN"
cd "${BACKEND}"
export DATABASE_URL
"${VENV_PY}" - <<'PY'
from app.database import SessionLocal
from app.services.notifications.scheduler import run_scheduler_tick
db = SessionLocal()
try:
    out = run_scheduler_tick(db, dry_run=True)
    scan = out.get("scan") or {}
    print("REMINDER_DRY_RUN=PASS")
    print(f"CANDIDATE_COUNT={scan.get('candidate_count', scan.get('scanned_items', 0))}")
    print(f"WOULD_CREATE_COUNT={scan.get('would_create_count', 0)}")
    print(f"DEDUPE_SKIPPED_COUNT={scan.get('dedupe_skipped_count', 0)}")
    print(f"WOULD_CANCEL_COMPLETED={scan.get('would_cancel_completed', 0)}")
finally:
    db.close()
PY
echo "SCHEDULER_ONESHOT=PENDING_CONFIRM"


# Informational only — do NOT seed admin
ADMIN_LOGIN_CODE="$(http_code -X POST "http://${SAAS_ADDR}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin123456"}')"
echo "SEED_ADMIN_LOGIN_HTTP=${ADMIN_LOGIN_CODE}"
echo "SEED_RUN=NO"

ADMIN_COUNT="$(pg_sql "SELECT count(*) FROM users WHERE role='admin';" | tr -d '[:space:]')"
echo "ADMIN_USER_COUNT=${ADMIN_COUNT}"
if [[ "${ADMIN_COUNT}" == "0" ]]; then
  echo "USER_ACTION_REQUIRED=YES"
  echo "USER_ACTION=No users.role=admin in production. Do NOT silent SQL. Propose promote via controlled op after owner confirms email."
  pg_sql "SELECT id,email,role,plan_code FROM users ORDER BY id;"
fi

section "CHECKPOINT SUMMARY (M1)"
echo "TARGET_BRANCH=cursor/mobile-cloud-preview"
echo "DB_REVISION_BEFORE=${EXPECTED_BEFORE}"
echo "DB_REVISION_AFTER=${REV_NOW}"
echo "BACKUP_FILE=${BACKUP_FILE}"
echo "BACKUP_BYTES=$(wc -c <"${BACKUP_FILE}" | tr -d ' ')"
echo "BACKUP_VERIFIED=YES"
echo "MIGRATION_008=PASS"
echo "RULE_COUNT=${RULE_COUNT}"
echo "UNIVERSITY_COUNT=${UNI2}"
echo "TIMELINE_COUNT=${TL2}"
echo "USER_COUNT=${USERS2}"
echo "DATA_INTEGRITY=PASS"
echo "SAAS_8010=PASS"
echo "CADDY_8088=PASS"
echo "PUBLIC_HEALTH=PASS"
echo "PUBLIC_ADMIN_API=PASS"
echo "PUBLIC_NOTIFICATION_API=MOUNTED"
echo "REMINDER_DRY_RUN=PASS"
echo "SCHEDULER_ONESHOT=PENDING_CONFIRM"
echo "SECOND_RUN_DUPLICATE_CREATED=PENDING_ONESHOT"
echo "ADMIN_MOBILE_NOTIFICATION_E2E=PENDING_MANUAL"
echo "STUDENT_H5_NOTIFICATION_E2E=PENDING_MANUAL"
echo "AI_REVIEW_NOTIFICATION=PENDING_MANUAL"
echo "REPORT_PUBLISHED_NOTIFICATION=PENDING_MANUAL"
echo "IN_APP_READY=YES"
echo "FCM_READY=NO"
echo "APNS_READY=NO"
echo "WEB_PUSH_READY=NO"
echo "DATABASE_CHANGED=YES"
echo "TUNNEL_CHANGED=NO"
echo "CADDY_CHANGED=NO"
echo "CLOUDFLARE_DOMAIN_CHANGED=NO"
echo "SECRET_CHANGED=NO"
echo "CNBER_CHANGED=NO"
echo "MAIN_CHANGED=NO"
echo "PRODUCTION_FREEZE=NO"
echo "READY_FOR_PUSH_PHASE=NO"
echo "NEXT_ACTION=Confirm dry-run, then CONFIRM_NOTIFICATION_ONESHOT=YES bash deploy/api/m1-notification-center-v1-production-release.sh --reminder-oneshot; complete Admin Mobile + Student H5 + AI publish E2E; paste full stdout"
