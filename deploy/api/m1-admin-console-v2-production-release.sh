#!/usr/bin/env bash
# M1 PRODUCTION RELEASE — Admin Console V2 (migration 011)
#
# DO NOT execute from this Cloud Agent turn.
# Staging acceptance only. PRODUCTION_MIGRATION_APPLIED=NO until a human runs on M1.
#
# Prerequisites on M1 (human):
#   1) Production tip contains 011_admin_console_v2.py + Admin Console V2 app code
#      (merge/ff this branch into cursor/mobile-cloud-preview first)
#   2) Current production revision is 010_student_crm_v1
#   3) Explicit approval, then:
#        bash deploy/api/m1-admin-console-v2-production-release.sh
#   Optional diagnostic:
#        bash deploy/api/m1-admin-console-v2-production-release.sh --checkpoint-d-diagnostic-only
#
# Does: fingerprint → backup (-Fc + pg_restore -l) → alembic 010→011 → integrity → kickstart SaaS
# Does NOT: main merge, CNber, tunnel recreate, Caddy route change, secret regen,
#           university/timeline mutation, staff creation, auto pg_restore, seed, sqlite
#
# 011 SAFETY (hard):
#   Additive only: users.account_kind / job_title / last_login_at / must_change_password
#   + ix_users_account_kind. No new tables. Never mutates universities (125),
#   admission timelines (900), membership, eligibility, notification_rules (51/CSCA24/non-CSCA27).
#   Backfill STAFF only when role is already a staff role. CUSTOMER must not flip to STAFF.
#
# PRODUCTION DB BINDING (hard):
#   container=huaqiao-postgres  host=127.0.0.1  port=5433  db=huaqiao  user=from container/env
#   Never bare host psql (socket :5432). Never assume role=postgres.
#   Never SQLite fallback. Fail closed. NO automatic pg_restore.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=deploy/api/lib/notification_008_schema_guard.sh
source "${ROOT}/deploy/api/lib/notification_008_schema_guard.sh"
# shellcheck source=deploy/api/lib/csca_009_integrity_guard.sh
source "${ROOT}/deploy/api/lib/csca_009_integrity_guard.sh"
# shellcheck source=deploy/api/lib/student_crm_010_schema_guard.sh
source "${ROOT}/deploy/api/lib/student_crm_010_schema_guard.sh"
# shellcheck source=deploy/api/lib/admin_console_011_schema_guard.sh
source "${ROOT}/deploy/api/lib/admin_console_011_schema_guard.sh"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ENV_FILE="${BACKEND}/.env"
BACKUP_DIR="${HOME}/guoqiao-backups"
PG_CONTAINER="huaqiao-postgres"
PG_DB="huaqiao"
PG_HOST="127.0.0.1"
PG_PORT="5433"
EXPECTED_BEFORE="010_student_crm_v1"
EXPECTED_AFTER="011_admin_console_v2"
EXPECTED_UNI=125
EXPECTED_TL=900
EXPECTED_PRE_NOTIFICATION_RULES=51
EXPECTED_POST_NOTIFICATION_RULES=51
EXPECTED_CSCA_RULES=24
EXPECTED_NON_CSCA_RULES=27
SAAS_LABEL="com.guoqiao.saas-backend"
CADDY_ADDR="127.0.0.1:8088"
SAAS_ADDR="127.0.0.1:8010"
ADMIN_ORIGIN="https://admin.guoqiaoplan.com"
APP_ORIGIN="https://app.guoqiaoplan.com"
PUBLIC_API="https://api.guoqiaoplan.com"
STAFF_ROLES_SQL="('admin','super_admin','operations_admin','consultant','support')"

MIGRATION_STARTED=NO
BACKUP_FILE=""
_PG_USER=""
_PG_PASS=""
_PG_DBNAME=""
DATABASE_URL=""
VENV_PY="${BACKEND}/.venv/bin/python"
DIAGNOSTIC_ONLY=NO
ROLLBACK_REQUIRED=NO

for _arg in "$@"; do
  case "${_arg}" in
    --checkpoint-d-diagnostic-only) DIAGNOSTIC_ONLY=YES ;;
    --help|-h)
      echo "Usage: $0 [--checkpoint-d-diagnostic-only]"
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
  echo "POSTGRES_USER=${_PG_USER}"
  echo "POSTGRES_DB=${PG_DB}"
  echo "POSTGRES_PASSWORD=***"
  echo "POSTGRES_ROLE_ASSUMPTION_BLOCKED=YES"
}

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
  echo "$1" | grep -oE '[0-9]{3}_[a-z0-9_]+' | head -1 || true
}

probe_011_objects() {
  _col() {
    pg_sql "SELECT CASE WHEN EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='users' AND column_name='$1'
    ) THEN 'YES' ELSE 'NO' END;" | tr -d '[:space:]'
  }
  ADMIN011_PROBE_ACCOUNT_KIND="$(_col account_kind)"
  ADMIN011_PROBE_JOB_TITLE="$(_col job_title)"
  ADMIN011_PROBE_LAST_LOGIN_AT="$(_col last_login_at)"
  ADMIN011_PROBE_MUST_CHANGE_PASSWORD="$(_col must_change_password)"
  ADMIN011_PROBE_INDEX="$(pg_sql "SELECT CASE WHEN EXISTS (
    SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ix_users_account_kind'
  ) THEN 'YES' ELSE 'NO' END;" | tr -d '[:space:]')"
}

evaluate_011_release_gate() {
  local rev="${1:-}"
  local total="${2:-0}"
  local csca="${3:-0}"
  local non_csca="${4:-0}"
  probe_011_objects
  classify_011_release_state \
    "${rev}" \
    "${total}" "${csca}" "${non_csca}" \
    "${ADMIN011_PROBE_ACCOUNT_KIND}" \
    "${ADMIN011_PROBE_JOB_TITLE}" \
    "${ADMIN011_PROBE_LAST_LOGIN_AT}" \
    "${ADMIN011_PROBE_MUST_CHANGE_PASSWORD}" \
    "${ADMIN011_PROBE_INDEX}"
}

staff_count_by_role() {
  pg_sql "SELECT count(*) FROM users WHERE lower(coalesce(role,'')) IN ${STAFF_ROLES_SQL};" | tr -d '[:space:]'
}

run_checkpoint_d_diagnostic() {
  section "CHECKPOINT D — DIAGNOSTIC (read-only)"
  echo "BACKEND_CWD=${BACKEND}"
  echo "ALEMBIC_INI=${BACKEND}/alembic.ini"
  echo "PYTHON=${VENV_PY}"
  echo "POSTGRES_TRANSACTIONAL_DDL=YES"
  [[ -x "${VENV_PY}" ]] || abort "missing ${VENV_PY} — SaaS .venv required (do not use system python3)"
  [[ -f "${BACKEND}/alembic.ini" ]] || abort "missing alembic.ini"
  [[ -f "${BACKEND}/alembic/versions/011_admin_console_v2.py" ]] || abort "missing 011 migration file"
  [[ -f "${BACKEND}/alembic/versions/010_student_crm_v1.py" ]] || abort "missing 010 migration file"
  echo "PYTHON_VERSION=$("${VENV_PY}" -c 'import sys; print(sys.version.split()[0])')"
  if ! "${VENV_PY}" -c 'import sqlalchemy, alembic' >/tmp/gq-p5-imp.err 2>&1; then
    echo "SQLALCHEMY_ALEMBIC_IMPORT=FAIL"
    abort "sqlalchemy/alembic import failed in .venv"
  fi
  echo "SQLALCHEMY_ALEMBIC_IMPORT=PASS"
  if ! "${VENV_PY}" -c 'import psycopg' >/tmp/gq-p5-psycopg.err 2>&1; then
    echo "PSYCOPG_IMPORT=FAIL"
    abort "psycopg (v3) import failed"
  fi
  echo "PSYCOPG_IMPORT=PASS"
  if echo "${DATABASE_URL}" | grep -qE ':5432/'; then
    abort "DATABASE_URL port 5432 blocked before alembic diagnostic"
  fi
  echo "${DATABASE_URL}" | grep -qE '@(127\.0\.0\.1|localhost):5433/huaqiao($|\?)' \
    || abort "DATABASE_URL not production 5433/huaqiao before alembic diagnostic"

  DIRECT_DB_REVISION="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
  echo "DIRECT_DB_REVISION=${DIRECT_DB_REVISION}"
  echo "DB_REVISION_BEFORE=${DIRECT_DB_REVISION}"

  CSCA_IN_SQL="$(csca_009_event_types_sql_in_list)"
  CSCA_RULE_COUNT="$(pg_sql "SELECT count(*) FROM notification_rules WHERE event_type IN ${CSCA_IN_SQL};" | tr -d '[:space:]')"
  NON_CSCA_RULE_COUNT="$(pg_sql "SELECT count(*) FROM notification_rules WHERE event_type NOT IN ${CSCA_IN_SQL};" | tr -d '[:space:]')"
  TOTAL_RULE_COUNT="$(pg_sql "SELECT count(*) FROM notification_rules;" | tr -d '[:space:]')"
  echo "CSCA_RULE_COUNT=${CSCA_RULE_COUNT}"
  echo "NON_CSCA_RULE_COUNT=${NON_CSCA_RULE_COUNT}"
  echo "TOTAL_RULE_COUNT=${TOTAL_RULE_COUNT}"

  echo "=== 011 RELEASE GATE ==="
  echo "OLD_008_GATE_INFORMATIONAL_ONLY=YES"
  echo "OLD_009_GATE_INFORMATIONAL_ONLY=YES"
  echo "OLD_010_GATE_NOT_USED_FOR_011_APPLY=YES"
  echo "CUSTOMER_STAFF_BACKFILL_POLICY=existing_role_in_staff_set_only"
  echo "EXISTING_MEMBER_STAYS_CUSTOMER=YES"
  echo "EXISTING_ADMIN_KEEPS_CONSOLE=YES"
  echo "NO_CUSTOMER_AUTO_PROMOTED_TO_STAFF=YES"
  evaluate_011_release_gate "${DIRECT_DB_REVISION}" "${TOTAL_RULE_COUNT}" "${CSCA_RULE_COUNT}" "${NON_CSCA_RULE_COUNT}"
  echo "CHECKPOINT_D_DIAGNOSTIC=PASS"

  set +e
  cur_out="$(alembic_bound current 2>/tmp/gq-p5-alembic-current.err)"
  cur_rc=$?
  heads_out="$(alembic_bound heads 2>/tmp/gq-p5-alembic-heads.err)"
  heads_rc=$?
  set -e
  echo "${cur_out}"
  echo "${heads_out}"
  ALEMBIC_CURRENT="$(normalize_rev "${cur_out}")"
  ALEMBIC_HEADS="$(normalize_rev "${heads_out}")"
  echo "ALEMBIC_CURRENT=${ALEMBIC_CURRENT}"
  echo "ALEMBIC_HEADS=${ALEMBIC_HEADS}"
  echo "ALEMBIC_CURRENT_EXIT=${cur_rc}"
  echo "ALEMBIC_HEADS_EXIT=${heads_rc}"
  [[ "${cur_rc}" -eq 0 ]] || abort "alembic current failed (exit=${cur_rc})"
  [[ "${heads_rc}" -eq 0 ]] || abort "alembic heads failed (exit=${heads_rc})"
  [[ "${ALEMBIC_HEADS}" == "${EXPECTED_AFTER}" ]] || abort "alembic heads != ${EXPECTED_AFTER} (got ${ALEMBIC_HEADS})"
}

report_migration_failure() {
  local rc="$1"
  local errf="$2"
  echo "MIGRATION_FAIL_RC=${rc}"
  echo "ALEMBIC_UPGRADE_STDERR_REDACTED=$(redact_err_file "${errf}")"
  local after_rev
  after_rev="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" 2>/dev/null | tr -d '[:space:]' || echo UNKNOWN)"
  echo "DB_REVISION_AFTER_FAILED_ATTEMPT=${after_rev}"
  if [[ "${after_rev}" == "${EXPECTED_BEFORE}" ]]; then
    echo "PG_TRANSACTION_LIKELY_ROLLED_BACK=YES"
    echo "ROLLBACK_REQUIRED=NO"
    ROLLBACK_REQUIRED=NO
  else
    echo "ROLLBACK_REQUIRED=YES"
    ROLLBACK_REQUIRED=YES
  fi
  echo "HINT: Do NOT auto pg_restore. Backup retained at BACKUP_FILE=${BACKUP_FILE}"
}

echo "============================================================"
echo "GUOQIAO ADMIN CONSOLE V2 — PRODUCTION RELEASE (011)"
echo "ROOT=${ROOT}"
echo "DIAGNOSTIC_ONLY=${DIAGNOSTIC_ONLY}"
echo "CNBER_CHANGED=NO MAIN_CHANGED=NO SEED_RUN=NO SQLITE_FALLBACK=BLOCKED"
echo "AUTO_PG_RESTORE=NO FAIL_CLOSED=YES PRODUCTION_STAFF_CREATE=NO"
echo "============================================================"

section "CHECKPOINT B — PRECHECK"
cd "${ROOT}"
test -f "${BACKEND}/alembic/versions/011_admin_console_v2.py" || abort "011 migration file missing"
test -f "${BACKEND}/alembic/versions/010_student_crm_v1.py" || abort "010 migration file missing"
docker inspect -f '{{.State.Running}}' "${PG_CONTAINER}" 2>/dev/null | grep -qx true \
  || abort "huaqiao-postgres not running"
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP:"${PG_PORT}" -sTCP:LISTEN >/dev/null 2>&1 || abort "port ${PG_PORT} not listening"
elif command -v nc >/dev/null 2>&1; then
  nc -z "${PG_HOST}" "${PG_PORT}" 2>/dev/null || abort "port ${PG_PORT} refused"
fi

load_container_pg_creds
load_and_validate_database_url

CUR_REV="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
echo "CURRENT_DB_REVISION=${CUR_REV}"
echo "DB_REVISION_BEFORE=${CUR_REV}"
[[ "${CUR_REV}" == "${EXPECTED_BEFORE}" || "${CUR_REV}" == "${EXPECTED_AFTER}" ]] \
  || abort "unexpected alembic revision=${CUR_REV}"

UNI="$(pg_sql "SELECT count(*) FROM universities;" | tr -d '[:space:]')"
TL="$(pg_sql "SELECT count(*) FROM admission_schedules;" | tr -d '[:space:]')"
USERS="$(pg_sql "SELECT count(*) FROM users;" | tr -d '[:space:]')"
RULES_PRE="$(pg_sql "SELECT count(*) FROM notification_rules;" | tr -d '[:space:]')"
PRE_STAFF_COUNT="$(staff_count_by_role)"
PRE_CUSTOMER_COUNT="$((USERS - PRE_STAFF_COUNT))"
PRE_UNIVERSITY_COUNT="${UNI}"
PRE_TIMELINE_COUNT="${TL}"
PRE_USER_COUNT="${USERS}"
PRE_NOTIFICATION_RULE_COUNT="${RULES_PRE}"
echo "UNIVERSITY_COUNT=${UNI}"
echo "TIMELINE_COUNT=${TL}"
echo "USER_COUNT=${USERS}"
echo "PRE_USER_COUNT=${PRE_USER_COUNT}"
echo "PRE_STAFF_COUNT=${PRE_STAFF_COUNT}"
echo "PRE_CUSTOMER_COUNT=${PRE_CUSTOMER_COUNT}"
echo "PRE_NOTIFICATION_RULE_COUNT=${PRE_NOTIFICATION_RULE_COUNT}"
echo "DYNAMIC_PRE_USER_COUNT=YES"
echo "FIXED_USER_COUNT_REMOVED=YES"
if [[ "${CUR_REV}" == "${EXPECTED_BEFORE}" ]]; then
  validate_pre_fingerprint "${UNI}" "${TL}" "${USERS}" "${RULES_PRE}" || abort "pre-migration fingerprint failed"
else
  validate_pre_fingerprint "${UNI}" "${TL}" "${USERS}" "" || abort "pre-check fingerprint failed"
fi
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
STU_BEFORE="$(pg_sql "SELECT count(*) FROM student_master_profiles;" | tr -d '[:space:]')"
STI_BEFORE="$(pg_sql "SELECT count(*) FROM student_timeline_items;" | tr -d '[:space:]')"
echo "membership_plans=${PLANS_BEFORE} expert_consultations=${EC_BEFORE} eligibility_records=${ER_BEFORE}"
echo "student_master_profiles=${STU_BEFORE} student_timeline_items=${STI_BEFORE}"

if [[ "${CUR_REV}" == "${EXPECTED_AFTER}" ]]; then
  info "Already at 011 — skip migrate (idempotent continue)"
  SKIP_MIGRATE=YES
else
  [[ "${CUR_REV}" == "${EXPECTED_BEFORE}" ]] || abort "can only migrate from ${EXPECTED_BEFORE}"
  SKIP_MIGRATE=NO
fi

if [[ "${DIAGNOSTIC_ONLY}" == "YES" ]]; then
  run_checkpoint_d_diagnostic
  echo "PRODUCTION_DB_CHANGED=NO"
  echo "MIGRATION_STARTED=NO"
  echo "PRODUCTION_STAFF_CREATED=NO"
  echo "DIAGNOSTIC_ONLY_EXIT=YES"
  exit 0
fi

section "CHECKPOINT C — BACKUP"
echo "BACKUP_FINGERPRINT_PRE_USER_COUNT=${PRE_USER_COUNT}"
echo "BACKUP_FINGERPRINT_PRE_STAFF_COUNT=${PRE_STAFF_COUNT}"
echo "BACKUP_FINGERPRINT_PRE_CUSTOMER_COUNT=${PRE_CUSTOMER_COUNT}"
echo "BACKUP_FINGERPRINT_PRE_UNIVERSITY_COUNT=${PRE_UNIVERSITY_COUNT}"
echo "BACKUP_FINGERPRINT_PRE_TIMELINE_COUNT=${PRE_TIMELINE_COUNT}"
echo "BACKUP_FINGERPRINT_PRE_NOTIFICATION_RULE_COUNT=${PRE_NOTIFICATION_RULE_COUNT}"
mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}" || true
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/huaqiao_pre_011_admin_console_${TS}.dump"
CONTAINER_TMP="/tmp/huaqiao_pre_011_admin_console_${TS}.dump"
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
echo "AUTO_PG_RESTORE=NO"

run_checkpoint_d_diagnostic
CSCA_IN_SQL="$(csca_009_event_types_sql_in_list)"
CSCA_RULE_COUNT_BEFORE="$(pg_sql "SELECT count(*) FROM notification_rules WHERE event_type IN ${CSCA_IN_SQL};" | tr -d '[:space:]')"
NON_CSCA_RULE_COUNT_BEFORE="$(pg_sql "SELECT count(*) FROM notification_rules WHERE event_type NOT IN ${CSCA_IN_SQL};" | tr -d '[:space:]')"
TOTAL_RULE_COUNT_BEFORE="$(pg_sql "SELECT count(*) FROM notification_rules;" | tr -d '[:space:]')"
DIRECT_DB_REVISION="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
echo "=== 011 PRE-MIGRATE GATE ==="
evaluate_011_release_gate "${DIRECT_DB_REVISION}" "${TOTAL_RULE_COUNT_BEFORE}" "${CSCA_RULE_COUNT_BEFORE}" "${NON_CSCA_RULE_COUNT_BEFORE}"

if [[ "${SKIP_MIGRATE}" == "YES" || "${SKIP_011_MIGRATE}" == "YES" || "${SCHEMA_STATE_011}" == "B_ALREADY_011" ]]; then
  echo "MIGRATION=SKIPPED_ALREADY_011"
  SKIP_MIGRATE=YES
elif [[ "${ALLOW_011_UPGRADE}" == "YES" && "${SCHEMA_STATE_011}" == "A_CLEAN_PRE_011" ]]; then
  section "CHECKPOINT D — APPLY 011"
  echo "ALEMBIC_CWD=${BACKEND}"
  echo "ALEMBIC_PYTHON=${VENV_PY}"
  echo "USING_SYSTEM_PYTHON3_M_ALEMBIC=NO"
  [[ "${ALEMBIC_CURRENT}" == "${EXPECTED_BEFORE}" ]] || abort "refuse upgrade: ALEMBIC_CURRENT=${ALEMBIC_CURRENT}"
  [[ "${DIRECT_DB_REVISION}" == "${EXPECTED_BEFORE}" ]] || abort "refuse upgrade: DIRECT_DB_REVISION=${DIRECT_DB_REVISION}"
  [[ "${ALEMBIC_HEADS}" == "${EXPECTED_AFTER}" ]] || abort "refuse upgrade: ALEMBIC_HEADS=${ALEMBIC_HEADS}"
  [[ "${ALLOW_011_UPGRADE}" == "YES" ]] || abort "refuse upgrade: ALLOW_011_UPGRADE!=YES"
  MIGRATION_STARTED=YES
  echo "MIGRATION_STARTED=YES"
  set +e
  alembic_bound upgrade "${EXPECTED_AFTER}" >/tmp/gq-p5-alembic-upgrade.out 2>/tmp/gq-p5-alembic-upgrade.err
  up_rc=$?
  set -e
  grep -E '^ALEMBIC_BOUND_TARGET=' /tmp/gq-p5-alembic-upgrade.out 2>/dev/null || true
  if [[ "${up_rc}" -ne 0 ]]; then
    report_migration_failure "${up_rc}" /tmp/gq-p5-alembic-upgrade.err
    abort "alembic upgrade 011 failed — fail closed"
  fi
  AFTER="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
  echo "DB_REVISION_AFTER=${AFTER}"
  if [[ "${AFTER}" != "${EXPECTED_AFTER}" ]]; then
    report_migration_failure "rev_mismatch" /tmp/gq-p5-alembic-upgrade.err
    abort "upgrade did not land on 011 (got ${AFTER})"
  fi
  ROLLBACK_REQUIRED=NO
  echo "MIGRATION=PASS"
else
  abort "refuse upgrade: SCHEMA_STATE_011=${SCHEMA_STATE_011} ALLOW_011_UPGRADE=${ALLOW_011_UPGRADE}"
fi

section "CHECKPOINT E — SCHEMA VERIFY"
probe_011_objects
[[ "${ADMIN011_PROBE_ACCOUNT_KIND}" == "YES" ]] || abort "missing users.account_kind"
[[ "${ADMIN011_PROBE_JOB_TITLE}" == "YES" ]] || abort "missing users.job_title"
[[ "${ADMIN011_PROBE_LAST_LOGIN_AT}" == "YES" ]] || abort "missing users.last_login_at"
[[ "${ADMIN011_PROBE_MUST_CHANGE_PASSWORD}" == "YES" ]] || abort "missing users.must_change_password"
[[ "${ADMIN011_PROBE_INDEX}" == "YES" ]] || abort "missing ix_users_account_kind"
echo "011_SCHEMA_VERIFY=PASS"

CSCA_IN_SQL="$(csca_009_event_types_sql_in_list)"
RULE_COUNT="$(pg_sql "SELECT count(*) FROM notification_rules;" | tr -d '[:space:]')"
CSCA_RULE_COUNT="$(pg_sql "SELECT count(*) FROM notification_rules WHERE event_type IN ${CSCA_IN_SQL};" | tr -d '[:space:]')"
NON_CSCA_RULE_COUNT_AFTER="$(pg_sql "SELECT count(*) FROM notification_rules WHERE event_type NOT IN ${CSCA_IN_SQL};" | tr -d '[:space:]')"
echo "RULE_COUNT=${RULE_COUNT} CSCA_RULE_COUNT=${CSCA_RULE_COUNT} NON_CSCA_RULE_COUNT_AFTER=${NON_CSCA_RULE_COUNT_AFTER}"
[[ "${RULE_COUNT}" == "${EXPECTED_POST_NOTIFICATION_RULES}" ]] || abort "notification_rules != ${EXPECTED_POST_NOTIFICATION_RULES}"
[[ "${CSCA_RULE_COUNT}" == "${EXPECTED_CSCA_RULES}" ]] || abort "CSCA_RULE_COUNT != ${EXPECTED_CSCA_RULES}"
[[ "${NON_CSCA_RULE_COUNT_AFTER}" == "${EXPECTED_NON_CSCA_RULES}" ]] || abort "NON_CSCA_RULE_COUNT_AFTER != ${EXPECTED_NON_CSCA_RULES}"

DIRECT_DB_REVISION="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
evaluate_011_release_gate "${DIRECT_DB_REVISION}" "${RULE_COUNT}" "${CSCA_RULE_COUNT}" "${NON_CSCA_RULE_COUNT_AFTER}"
[[ "${SCHEMA_STATE_011}" == "B_ALREADY_011" ]] || abort "post-migrate 011 gate failed: ${SCHEMA_STATE_011}"

section "CHECKPOINT F — DATA INTEGRITY"
UNI2="$(pg_sql "SELECT count(*) FROM universities;" | tr -d '[:space:]')"
TL2="$(pg_sql "SELECT count(*) FROM admission_schedules;" | tr -d '[:space:]')"
USERS2="$(pg_sql "SELECT count(*) FROM users;" | tr -d '[:space:]')"
POST_STAFF_COUNT="$(pg_sql "SELECT count(*) FROM users WHERE account_kind='STAFF';" | tr -d '[:space:]')"
POST_CUSTOMER_COUNT="$(pg_sql "SELECT count(*) FROM users WHERE account_kind='CUSTOMER';" | tr -d '[:space:]')"
ILLEGAL_STAFF="$(pg_sql "SELECT count(*) FROM users WHERE account_kind='STAFF' AND lower(coalesce(role,'')) NOT IN ${STAFF_ROLES_SQL};" | tr -d '[:space:]')"
PLANS2="$(pg_sql "SELECT count(*) FROM membership_plans;" | tr -d '[:space:]')"
EC2="$(pg_sql "SELECT count(*) FROM expert_consultations;" | tr -d '[:space:]')"
ER2="$(pg_sql "SELECT count(*) FROM eligibility_records;" | tr -d '[:space:]')"
STU2="$(pg_sql "SELECT count(*) FROM student_master_profiles;" | tr -d '[:space:]')"
STI2="$(pg_sql "SELECT count(*) FROM student_timeline_items;" | tr -d '[:space:]')"
REV_NOW="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
echo "DB_REVISION_AFTER=${REV_NOW}"
echo "POST_USER_COUNT=${USERS2}"
echo "POST_STAFF_COUNT=${POST_STAFF_COUNT}"
echo "POST_CUSTOMER_COUNT=${POST_CUSTOMER_COUNT}"
echo "POST_UNIVERSITY_COUNT=${UNI2}"
echo "POST_TIMELINE_COUNT=${TL2}"
[[ "${REV_NOW}" == "${EXPECTED_AFTER}" ]] || abort "revision after migrate != 011"
validate_post_integrity \
  "${PRE_USER_COUNT}" "${USERS2}" \
  "${PRE_UNIVERSITY_COUNT}" "${UNI2}" \
  "${PRE_TIMELINE_COUNT}" "${TL2}" \
  "${RULE_COUNT}" "${CSCA_RULE_COUNT}" "${NON_CSCA_RULE_COUNT_AFTER}" \
  || abort "post-migration integrity failed"
validate_011_account_kind_integrity \
  "${PRE_USER_COUNT}" "${PRE_STAFF_COUNT}" \
  "${USERS2}" "${POST_STAFF_COUNT}" "${POST_CUSTOMER_COUNT}" "${ILLEGAL_STAFF}" \
  || abort "CUSTOMER/STAFF account_kind integrity failed"
[[ "${PLANS2}" == "${PLANS_BEFORE}" ]] || abort "membership_plans count changed"
[[ "${EC2}" == "${EC_BEFORE}" ]] || abort "expert_consultations count changed"
[[ "${ER2}" == "${ER_BEFORE}" ]] || abort "eligibility_records count changed"
[[ "${STU2}" == "${STU_BEFORE}" ]] || abort "student_master_profiles count changed"
[[ "${STI2}" == "${STI_BEFORE}" ]] || abort "student_timeline_items count changed"
echo "DATA_INTEGRITY=PASS"
echo "CUSTOMER_NOT_FLIPPED_TO_STAFF=PASS"
echo "PRODUCTION_STAFF_CREATED=NO"

section "CHECKPOINT G — RESTART SAAS"
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
        for o in (admin, app):
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
EMP_CODE="$(http_code "http://${SAAS_ADDR}/api/admin/v1/employees")"
NAV_CODE="$(http_code "http://${SAAS_ADDR}/api/admin/v1/nav")"
echo "ADMIN_V1_EMPLOYEES_HTTP=${EMP_CODE}"
echo "ADMIN_V1_NAV_HTTP=${NAV_CODE}"
[[ "${EMP_CODE}" != "404" && "${NAV_CODE}" != "404" ]] || abort "admin console v2 routes still 404"
CC2="$(http_code "http://${CADDY_ADDR}/api/health")"
PH="$(http_code "${PUBLIC_API}/api/health")"
echo "CADDY_8088=${CC2} PUBLIC_HEALTH=${PH}"
[[ "${CC2}" == "200" ]] || abort "Caddy health after restart != 200"
[[ "${PH}" == "200" ]] || abort "public health != 200"

section "CHECKPOINT SUMMARY (M1)"
echo "TARGET_BRANCH=cursor/mobile-cloud-preview"
echo "DB_REVISION_BEFORE=${EXPECTED_BEFORE}"
echo "DB_REVISION_AFTER=${REV_NOW}"
echo "BACKUP_FILE=${BACKUP_FILE}"
echo "BACKUP_VERIFIED=YES"
echo "MIGRATION_011=PASS"
echo "PRE_USER_COUNT=${PRE_USER_COUNT}"
echo "POST_USER_COUNT=${USERS2}"
echo "PRE_STAFF_COUNT=${PRE_STAFF_COUNT}"
echo "POST_STAFF_COUNT=${POST_STAFF_COUNT}"
echo "PRE_CUSTOMER_COUNT=${PRE_CUSTOMER_COUNT}"
echo "POST_CUSTOMER_COUNT=${POST_CUSTOMER_COUNT}"
echo "UNIVERSITY_COUNT=${UNI2}"
echo "TIMELINE_COUNT=${TL2}"
echo "RULE_COUNT=${RULE_COUNT}"
echo "DATA_INTEGRITY=PASS"
echo "PRODUCTION_STAFF_CREATED=NO"
echo "SEED_RUN=NO"
echo "TUNNEL_CHANGED=NO"
echo "CADDY_CHANGED=NO"
echo "CLOUDFLARE_DOMAIN_CHANGED=NO"
echo "SECRET_CHANGED=NO"
echo "CNBER_CHANGED=NO"
echo "MAIN_CHANGED=NO"
echo "AUTO_PG_RESTORE=NO"
echo "NEXT_ACTION=Human verifies four-role login on production admin; do not create production staff from Cloud Agent"
