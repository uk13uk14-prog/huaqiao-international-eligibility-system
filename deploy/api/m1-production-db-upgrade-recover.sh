#!/usr/bin/env bash
# M1 production DB upgrade + SaaS runtime recovery (FAIL CLOSED checkpoints).
# Path: 003_r43_fix → 004 → 005 → 006_student_profile_slots
#
# Touches ONLY container: huaqiao-postgres
# Never: docker compose down, docker system prune, broad stop/kill, CNber, seed rewrite,
#        invent JWT/VAULT (search-only), print passwords / full DATABASE_URL
#
# Usage:
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   bash deploy/api/m1-production-db-upgrade-recover.sh
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
VENV_PY="${BACKEND}/.venv/bin/python"
VENV_ALEMBIC="${BACKEND}/.venv/bin/alembic"
PG_CONTAINER="huaqiao-postgres"
PG_DB="huaqiao"
PG_HOST="127.0.0.1"
PG_PORT="5433"
EXPECTED_REV="003_r43_fix"
TARGET_REV="006_student_profile_slots"
EXPECTED_UNI=125
EXPECTED_TL=900
BACKUP_DIR="${HOME}/guoqiao-backups"
STATE_DIR="${HOME}/.guoqiao/saas"
RUNTIME_ENV="${STATE_DIR}/runtime.env"
PLIST_LABEL="com.guoqiao.saas-backend"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
RUN_WRAPPER="${ROOT}/deploy/api/m1-saas-backend-run.sh"
GUARD="${ROOT}/deploy/api/production-db-guard.sh"
SKIP_GO_LIVE="${SKIP_GO_LIVE:-0}"
SKIP_TUNNEL="${SKIP_TUNNEL:-0}"

# Secrets held only in locals — never echo
_PG_USER=""
_PG_PASS=""
_PG_DBNAME=""
DATABASE_URL_REDACTED=""
BACKUP_FILE=""
CONTAINER_TMP=""
TS=""
ROLLBACK_REQUIRED=NO
MIGRATION_STARTED=NO
USER_ACTION_REQUIRED=NO

abort() {
  echo "ABORT: $*" >&2
  echo "ROLLBACK_REQUIRED=${ROLLBACK_REQUIRED}"
  echo "MIGRATION_STARTED=${MIGRATION_STARTED}"
  if [[ -n "${BACKUP_FILE}" ]]; then
    echo "BACKUP_FILE=${BACKUP_FILE}"
  fi
  echo "HINT: Do NOT auto pg_restore. Manual approve required for restore."
  exit 1
}

checkpoint() { echo; echo "######## CHECKPOINT $* ########"; }
info() { echo "==> $*"; }
redact_url() {
  echo "$1" | sed -E 's#(://[^:/@]+:)[^@/]+@#\1***@#g'
}

# Refuse dangerous patterns early
assert_safe_context() {
  case "$*" in
    *'docker compose down'*|*'docker-compose down'*|*'system prune'*|*'killall'* ) abort "forbidden command pattern" ;;
  esac
}

pg_sql() {
  docker exec "${PG_CONTAINER}" psql -U "${_PG_USER}" -d "${PG_DB}" -v ON_ERROR_STOP=1 -tAc "$1"
}

table_exists() {
  local r
  r="$(pg_sql "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='$1' LIMIT 1;" || true)"
  [[ "$(echo "$r" | tr -d '[:space:]')" == "1" ]]
}

count_or_fail() {
  local t="$1"
  local c
  c="$(pg_sql "SELECT count(*) FROM ${t};")"
  echo "$(echo "$c" | tr -d '[:space:]')"
}

echo "============================================================"
echo "GUOQIAO M1 PRODUCTION DB UPGRADE + RECOVERY"
echo "ROOT=${ROOT}"
echo "HEAD=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "TARGET=${EXPECTED_REV} -> ${TARGET_REV}"
echo "CNBER_GUARD=YES BETA_GUARD=YES SEED_ALLOWED=NO SQLITE_FALLBACK=BLOCKED"
echo "============================================================"

# ---------- Load container credentials (never print password) ----------
docker inspect "${PG_CONTAINER}" >/dev/null 2>&1 || abort "container ${PG_CONTAINER} missing"
while IFS= read -r ev; do
  case "$ev" in
    POSTGRES_USER=*) _PG_USER="${ev#POSTGRES_USER=}" ;;
    POSTGRES_PASSWORD=*) _PG_PASS="${ev#POSTGRES_PASSWORD=}" ;;
    POSTGRES_DB=*) _PG_DBNAME="${ev#POSTGRES_DB=}" ;;
  esac
done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${PG_CONTAINER}")
[[ -n "${_PG_USER}" ]] || abort "POSTGRES_USER missing from container"
[[ -n "${_PG_PASS}" ]] || abort "POSTGRES_PASSWORD missing from container"
[[ -n "${_PG_DBNAME}" ]] || abort "POSTGRES_DB missing from container"
[[ "${_PG_DBNAME}" == "${PG_DB}" ]] || abort "POSTGRES_DB=${_PG_DBNAME} != expected ${PG_DB}"
echo "POSTGRES_USER=${_PG_USER}"
echo "POSTGRES_DB=${PG_DB}"
echo "POSTGRES_PASSWORD=***"

# =====================================================================
checkpoint "A DATABASE_IDENTITY"
# =====================================================================
# Port 5433
if command -v lsof >/dev/null 2>&1; then
  lsof -nP -iTCP:"${PG_PORT}" -sTCP:LISTEN >/dev/null 2>&1 || abort "port ${PG_PORT} not listening"
elif command -v nc >/dev/null 2>&1; then
  nc -z "${PG_HOST}" "${PG_PORT}" 2>/dev/null || abort "port ${PG_PORT} refused"
fi

CUR_REV="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" || true)"
CUR_REV="$(echo "${CUR_REV}" | tr -d '[:space:]')"
echo "CURRENT_DB_REVISION=${CUR_REV}"
[[ "${CUR_REV}" == "${EXPECTED_REV}" ]] || abort "expected revision ${EXPECTED_REV}, got ${CUR_REV}"

UNI="$(count_or_fail universities)"
TL="$(count_or_fail admission_schedules)"
USERS="$(count_or_fail users)"
MEMB="$(count_or_fail membership_plans)"
VAULT=0
ELIG=0
table_exists customer_vaults && VAULT="$(count_or_fail customer_vaults)"
table_exists eligibility_records && ELIG="$(count_or_fail eligibility_records)"
echo "UNIVERSITY_COUNT=${UNI}"
echo "TIMELINE_COUNT=${TL}"
echo "USER_COUNT=${USERS}"
echo "MEMBERSHIP_COUNT=${MEMB}"
[[ "${UNI}" == "${EXPECTED_UNI}" ]] || abort "universities ${UNI} != ${EXPECTED_UNI}"
[[ "${TL}" == "${EXPECTED_TL}" ]] || abort "schedules ${TL} != ${EXPECTED_TL}"
echo "DATABASE_IDENTITY_CHECK=PASS"

# =====================================================================
checkpoint "B PRE-MIGRATION BACKUP"
# =====================================================================
mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}" || true
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/huaqiao_pre_006_${TS}.dump"
CONTAINER_TMP="/tmp/huaqiao_pre_006_${TS}.dump"

info "pg_dump -Fc inside ${PG_CONTAINER}"
docker exec "${PG_CONTAINER}" pg_dump -U "${_PG_USER}" -d "${PG_DB}" -Fc -f "${CONTAINER_TMP}" \
  || abort "pg_dump failed"

info "docker cp -> ${BACKUP_FILE}"
docker cp "${PG_CONTAINER}:${CONTAINER_TMP}" "${BACKUP_FILE}" \
  || abort "docker cp backup failed"

[[ -f "${BACKUP_FILE}" ]] || abort "BACKUP_FILE_EXISTS=NO"
sz="$(wc -c < "${BACKUP_FILE}" | tr -d ' ')"
echo "BACKUP_BYTES=${sz}"
[[ "${sz}" -gt 0 ]] || abort "BACKUP_NONZERO=NO"

info "pg_restore -l (container temp)"
if ! docker exec "${PG_CONTAINER}" pg_restore -l "${CONTAINER_TMP}" >/tmp/gq-pg-restore-list.txt 2>/tmp/gq-pg-restore-list.err; then
  cat /tmp/gq-pg-restore-list.err >&2 || true
  abort "PG_RESTORE_LIST=FAIL"
fi
list_lines="$(wc -l < /tmp/gq-pg-restore-list.txt | tr -d ' ')"
[[ "${list_lines}" -gt 5 ]] || abort "PG_RESTORE_LIST too short (${list_lines})"
# Host-side verify via postgres image if available (optional reinforce)
if docker image inspect postgres:16 >/dev/null 2>&1; then
  docker run --rm -v "${BACKUP_DIR}:/backups:ro" postgres:16 \
    pg_restore -l "/backups/$(basename "${BACKUP_FILE}")" >/tmp/gq-pg-restore-host.txt 2>/dev/null \
    || abort "host pg_restore -l failed"
fi

chmod 600 "${BACKUP_FILE}" || true
# Safe to remove container temp after verified copy
docker exec "${PG_CONTAINER}" rm -f "${CONTAINER_TMP}" || true
echo "BACKUP_FILE_EXISTS=YES"
echo "BACKUP_NONZERO=YES"
echo "PG_RESTORE_LIST=PASS"
echo "BACKUP_VERIFIED=YES"
echo "BACKUP_FILE=${BACKUP_FILE}"

# =====================================================================
checkpoint "C PRE-MIGRATION FINGERPRINT"
# =====================================================================
PRE_REVISION="${CUR_REV}"
PRE_UNIVERSITY_COUNT="${UNI}"
PRE_TIMELINE_COUNT="${TL}"
PRE_USER_COUNT="${USERS}"
PRE_MEMBERSHIP_COUNT="${MEMB}"
PRE_CUSTOMER_VAULT_COUNT="${VAULT}"
PRE_ELIGIBILITY_RECORD_COUNT="${ELIG}"
echo "PRE_REVISION=${PRE_REVISION}"
echo "PRE_UNIVERSITY_COUNT=${PRE_UNIVERSITY_COUNT}"
echo "PRE_TIMELINE_COUNT=${PRE_TIMELINE_COUNT}"
echo "PRE_USER_COUNT=${PRE_USER_COUNT}"
echo "PRE_MEMBERSHIP_COUNT=${PRE_MEMBERSHIP_COUNT}"
echo "PRE_CUSTOMER_VAULT_COUNT=${PRE_CUSTOMER_VAULT_COUNT}"
echo "PRE_ELIGIBILITY_RECORD_COUNT=${PRE_ELIGIBILITY_RECORD_COUNT}"

# =====================================================================
checkpoint "D DATABASE_URL / .env"
# =====================================================================
# URL-encode password (never print)
ENCODED_PASS="$(
  _GQ_PASS="${_PG_PASS}" "${VENV_PY}" -c 'import os; from urllib.parse import quote; print(quote(os.environ["_GQ_PASS"], safe=""), end="")' \
  2>/dev/null \
  || _GQ_PASS="${_PG_PASS}" python3 -c 'import os; from urllib.parse import quote; print(quote(os.environ["_GQ_PASS"], safe=""), end="")'
)"
[[ -n "${ENCODED_PASS}" ]] || abort "password URL encoding failed"
REAL_URL="postgresql+psycopg://${_PG_USER}:${ENCODED_PASS}@${PG_HOST}:${PG_PORT}/${PG_DB}"
DATABASE_URL_REDACTED="$(redact_url "${REAL_URL}")"
echo "DATABASE_URL_REDACTED=${DATABASE_URL_REDACTED}"
echo "PASSWORD_URL_ENCODING=YES"

ENV_FILE="${BACKEND}/.env"
if [[ -f "${ENV_FILE}" ]]; then
  info ".env exists — will not overwrite; verifying DATABASE_URL target"
  existing="$(
    "${VENV_PY}" -c "
from pathlib import Path
p=Path(r'''${ENV_FILE}''')
url=''
for line in p.read_text(encoding='utf-8').splitlines():
    if line.strip().startswith('DATABASE_URL='):
        url=line.split('=',1)[1].strip().strip(chr(34)).strip(chr(39))
        break
print(url)
" 2>/dev/null || true
  )"
  [[ -n "${existing}" ]] || abort "existing .env has no DATABASE_URL"
  existing_redacted="$(redact_url "${existing}")"
  echo "EXISTING_DATABASE_URL_REDACTED=${existing_redacted}"
  case "${existing}" in
    *"${PG_HOST}:${PG_PORT}/${PG_DB}"*|*"@127.0.0.1:${PG_PORT}/${PG_DB}"*|*"@localhost:${PG_PORT}/${PG_DB}"*)
      info "existing .env points at same host/db — keeping file"
      ;;
    *)
      abort "existing .env DATABASE_URL does not target ${PG_HOST}:${PG_PORT}/${PG_DB}"
      ;;
  esac
else
  info "creating ${ENV_FILE} (mode 600) — DATABASE_URL + skip-seed + known public CORS only"
  FOUND_JWT=""
  FOUND_VAULT=""
  for cand in \
    "${HOME}/.guoqiao/saas/.env" \
    "${HOME}/.config/guoqiao/saas.env" \
    "${ROOT}/.env" \
    "${BACKEND}/.env.local"
  do
    [[ -f "$cand" ]] || continue
    while IFS= read -r line; do
      case "$line" in
        JWT_SECRET_KEY=*) [[ -z "${FOUND_JWT}" ]] && FOUND_JWT="${line#JWT_SECRET_KEY=}" ;;
        VAULT_FERNET_KEY=*) [[ -z "${FOUND_VAULT}" ]] && FOUND_VAULT="${line#VAULT_FERNET_KEY=}" ;;
      esac
    done < "$cand"
  done

  umask 077
  {
    echo "# Generated by m1-production-db-upgrade-recover.sh — DO NOT COMMIT"
    echo "DATABASE_URL=${REAL_URL}"
    echo "GUOQIAO_SKIP_SEED=1"
    echo "PUBLIC_BASE_URL=https://api.guoqiaoplan.com"
    echo "FRONTEND_BASE_URL=https://app.guoqiaoplan.com"
    echo "CORS_ORIGINS=https://app.guoqiaoplan.com,https://huaqiao-international-eligibility-system.rambolluk.workers.dev"
    if [[ -n "${FOUND_JWT}" ]]; then
      echo "JWT_SECRET_KEY=${FOUND_JWT}"
    else
      echo "# JWT_SECRET_KEY=  # REQUIRED — not found; set before starting :8010"
    fi
    if [[ -n "${FOUND_VAULT}" ]]; then
      echo "VAULT_FERNET_KEY=${FOUND_VAULT}"
    else
      echo "# VAULT_FERNET_KEY=  # REQUIRED — not found; set before starting :8010"
    fi
  } > "${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
  unset FOUND_JWT FOUND_VAULT
fi

# git check-ignore
if git -C "${ROOT}" check-ignore -q "huaqiao-saas-pro/backend/.env"; then
  echo "GIT_CHECK_IGNORE_ENV=PASS"
else
  abort "backend/.env is not gitignored"
fi
echo "ENV_READY=YES"

# Clear password vars from shell where possible after URL built
# Keep DB_URL for alembic binding (never echo). Prefer existing .env contents.
DB_URL="$(
  "${VENV_PY}" -c "
from pathlib import Path
p=Path(r'''${ENV_FILE}''')
for line in p.read_text(encoding='utf-8').splitlines():
    if line.strip().startswith('DATABASE_URL='):
        print(line.split('=',1)[1].strip().strip(chr(34)).strip(chr(39)), end='')
        break
"
)"
[[ -n "${DB_URL}" ]] || abort "DB_URL empty after .env load"
DATABASE_URL_REDACTED="$(redact_url "${DB_URL}")"
echo "ENV_DATABASE_TARGET=$(echo "${DATABASE_URL_REDACTED}" | sed -E 's#^[^@]+@##')"
unset _PG_PASS ENCODED_PASS REAL_URL

# =====================================================================
checkpoint "E PYTHON DRIVER"
# =====================================================================
[[ -x "${VENV_PY}" ]] || abort "missing ${VENV_PY} — run m1-saas-runtime-recover.sh first"
info "Python=$("${VENV_PY}" -c 'import sys; print(sys.version.split()[0])')"
if ! "${VENV_PY}" -c 'import sqlalchemy, alembic' >/dev/null 2>&1; then
  abort "sqlalchemy/alembic import failed in .venv"
fi
if ! "${VENV_PY}" -c 'import psycopg' >/dev/null 2>&1; then
  info "psycopg missing — installing into .venv only (requirements.txt)"
  "${BACKEND}/.venv/bin/pip" install 'psycopg[binary]==3.2.3' \
    || abort "failed to install psycopg into .venv"
fi
"${VENV_PY}" -c 'import psycopg; print("PSYCOPG_IMPORT=PASS")' || abort "PSYCOPG_IMPORT=FAIL"
echo "SYSTEM_PYTHON_MODIFIED=NO"

# Helper: run alembic with explicit DATABASE_URL (ConfigParser needs % → %% in set_main_option).
# Never prints URL/password. Always uses BACKEND as cwd + alembic.ini there.
alembic_bound() {
  # usage: alembic_bound current|heads|upgrade head|...
  local op="$1"
  shift || true
  (
    cd "${BACKEND}" || exit 1
    export DATABASE_URL="${DB_URL}"
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

# Prove binding target without secrets
m = re.search(r"@([^/]+)/(\S+)", url)
target = f"{m.group(1)}/{m.group(2)}" if m else "UNKNOWN"
print(f"ALEMBIC_BOUND_TARGET={target}")

cfg = Config(os.path.join(backend, "alembic.ini"))
# CRITICAL: ConfigParser interpolation treats % specially
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
    # Redact any URL-like substrings from error
    msg = str(e)
    msg = re.sub(r"postgresql\+?[^\s]+", "postgresql+psycopg://***", msg)
    msg = re.sub(r":[^:@/]+@", ":***@", msg)
    print(f"ALEMBIC_BIND_ERROR={msg}", file=sys.stderr)
    raise SystemExit(1)
PY
  )
}

# =====================================================================
checkpoint "F ALEMBIC DRY INSPECTION"
# =====================================================================
echo "BACKEND_CWD=${BACKEND}"
echo "ALEMBIC_INI=${BACKEND}/alembic.ini"
[[ -f "${BACKEND}/alembic.ini" ]] || abort "missing alembic.ini"
[[ -f "${BACKEND}/alembic/versions/004_student_master_profile.py" ]] || abort "missing 004"
[[ -f "${BACKEND}/alembic/versions/005_student_timeline.py" ]] || abort "missing 005"
[[ -f "${BACKEND}/alembic/versions/006_student_profile_slots.py" ]] || abort "missing 006"

# Verify chain in files
down004="$(grep -E '^down_revision' "${BACKEND}/alembic/versions/004_student_master_profile.py" | head -1)"
down005="$(grep -E '^down_revision' "${BACKEND}/alembic/versions/005_student_timeline.py" | head -1)"
down006="$(grep -E '^down_revision' "${BACKEND}/alembic/versions/006_student_profile_slots.py" | head -1)"
echo "$down004" | grep -q '003_r43_fix' || abort "004 down_revision invalid"
echo "$down005" | grep -q '004_student_master_profile' || abort "005 down_revision invalid"
echo "$down006" | grep -q '005_student_timeline' || abort "006 down_revision invalid"

# A) Direct SQL revision (same as Checkpoint A)
DIRECT_DB_REVISION="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;")"
DIRECT_DB_REVISION="$(echo "${DIRECT_DB_REVISION}" | tr -d '[:space:]')"
echo "DIRECT_DB_REVISION=${DIRECT_DB_REVISION}"
[[ "${DIRECT_DB_REVISION}" == "${EXPECTED_REV}" ]] || abort "direct SQL revision != ${EXPECTED_REV}"

# Settings load check (redacted) — cwd=BACKEND so .env resolves
SETTINGS_TARGET="$(
  cd "${BACKEND}" && DATABASE_URL="${DB_URL}" "${VENV_PY}" - <<'PY'
import os, re
os.environ["DATABASE_URL"] = os.environ["DATABASE_URL"]
from app.config import get_settings
get_settings.cache_clear()
u = get_settings().database_url
m = re.search(r"@([^/]+)/(\S+)", u)
print(f"{m.group(1)}/{m.group(2)}" if m else "UNKNOWN")
PY
)"
echo "SETTINGS_DATABASE_TARGET=${SETTINGS_TARGET}"
echo "${SETTINGS_TARGET}" | grep -q "${PG_PORT}/${PG_DB}" || abort "settings.database_url not bound to :${PG_PORT}/${PG_DB}"

# B) Alembic current with explicit binding
cur_out="$(alembic_bound current 2>/tmp/gq-alembic-current.err || true)"
cur_err="$(cat /tmp/gq-alembic-current.err 2>/dev/null | sed -E 's#(://[^:/@]+:)[^@/]+@#\1***@#g' || true)"
echo "${cur_out}"
[[ -z "${cur_err}" ]] || echo "ALEMBIC_CURRENT_STDERR_REDACTED=${cur_err}"
ALEMBIC_CURRENT_CLI="$(echo "${cur_out}" | grep -E "${EXPECTED_REV}|${TARGET_REV}" | head -1 | tr -d '[:space:]' || true)"
# alembic current prints like: "003_r43_fix (head)" or just revision — normalize
ALEMBIC_CURRENT_CLI="$(echo "${cur_out}" | grep -oE '[0-9]{3}_[a-z0-9_]+' | head -1 || true)"
echo "ALEMBIC_CURRENT_CLI=${ALEMBIC_CURRENT_CLI}"
[[ "${ALEMBIC_CURRENT_CLI}" == "${EXPECTED_REV}" ]] || abort "alembic current != ${EXPECTED_REV} (got '${ALEMBIC_CURRENT_CLI}') — check ALEMBIC_BOUND_TARGET"

# C) Alembic heads
heads_out="$(alembic_bound heads 2>/tmp/gq-alembic-heads.err || true)"
echo "${heads_out}"
ALEMBIC_HEADS="$(echo "${heads_out}" | grep -oE '[0-9]{3}_[a-z0-9_]+' | head -1 || true)"
echo "ALEMBIC_HEADS=${ALEMBIC_HEADS}"
[[ "${ALEMBIC_HEADS}" == "${TARGET_REV}" ]] || abort "alembic heads != ${TARGET_REV}"

echo "EXPLICIT_DATABASE_URL_BINDING=YES"
echo "ALEMBIC_CHAIN_VALID=YES"
echo "MIGRATION_PATH=003→004→005→006"

# =====================================================================
checkpoint "G MIGRATION"
# =====================================================================
echo "MIGRATION_STARTED=YES"
MIGRATION_STARTED=YES
ROLLBACK_REQUIRED=YES  # until post-checks pass
if ! alembic_bound upgrade head; then
  abort "alembic upgrade head FAILED — backup retained; do NOT auto-restore"
fi
POST_REV="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;")"
POST_REV="$(echo "${POST_REV}" | tr -d '[:space:]')"
echo "CURRENT_DB_REVISION=${POST_REV}"
[[ "${POST_REV}" == "${TARGET_REV}" ]] || abort "MIGRATION=FAIL revision=${POST_REV}"
echo "MIGRATION=PASS"

# =====================================================================
checkpoint "H POST-MIGRATION SCHEMA"
# =====================================================================
table_exists student_master_profiles || abort "student_master_profiles missing"
table_exists student_timeline_items || abort "student_timeline_items missing"
cols_stu="$(pg_sql "SELECT string_agg(column_name, ',' ORDER BY column_name) FROM information_schema.columns WHERE table_schema='public' AND table_name='student_master_profiles';")"
cols_users="$(pg_sql "SELECT string_agg(column_name, ',' ORDER BY column_name) FROM information_schema.columns WHERE table_schema='public' AND table_name='users';")"
echo "STUDENT_MASTER_PROFILE_COLUMNS=${cols_stu}"
echo "USERS_COLUMNS=${cols_users}"
echo "${cols_stu}" | grep -q 'status' || abort "missing status column"
echo "${cols_stu}" | grep -q 'archived_at' || abort "missing archived_at"
echo "${cols_stu}" | grep -q 'deleted_at' || abort "missing deleted_at"
echo "${cols_users}" | grep -q 'student_profile_limit_override' || abort "missing student_profile_limit_override"
echo "SCHEMA_CURRENT=YES"

# =====================================================================
checkpoint "I DATA INTEGRITY"
# =====================================================================
POST_UNIVERSITY_COUNT="$(count_or_fail universities)"
POST_TIMELINE_COUNT="$(count_or_fail admission_schedules)"
POST_USER_COUNT="$(count_or_fail users)"
POST_MEMBERSHIP_COUNT="$(count_or_fail membership_plans)"
POST_CUSTOMER_VAULT_COUNT="$(count_or_fail customer_vaults)"
POST_ELIGIBILITY_RECORD_COUNT="$(count_or_fail eligibility_records)"
STUDENT_MASTER_PROFILE_COUNT="$(count_or_fail student_master_profiles)"
STUDENT_TIMELINE_COUNT="$(count_or_fail student_timeline_items)"

echo "POST_UNIVERSITY_COUNT=${POST_UNIVERSITY_COUNT}"
echo "POST_TIMELINE_COUNT=${POST_TIMELINE_COUNT}"
echo "POST_USER_COUNT=${POST_USER_COUNT}"
echo "POST_MEMBERSHIP_COUNT=${POST_MEMBERSHIP_COUNT}"
echo "STUDENT_MASTER_PROFILE_COUNT=${STUDENT_MASTER_PROFILE_COUNT}"
echo "STUDENT_TIMELINE_COUNT=${STUDENT_TIMELINE_COUNT}"

[[ "${POST_UNIVERSITY_COUNT}" == "${PRE_UNIVERSITY_COUNT}" ]] || abort "DATA_INTEGRITY universities changed"
[[ "${POST_TIMELINE_COUNT}" == "${PRE_TIMELINE_COUNT}" ]] || abort "DATA_INTEGRITY schedules changed"
[[ "${POST_USER_COUNT}" == "${PRE_USER_COUNT}" ]] || abort "DATA_INTEGRITY users changed"
[[ "${POST_MEMBERSHIP_COUNT}" == "${PRE_MEMBERSHIP_COUNT}" ]] || abort "DATA_INTEGRITY membership changed"
[[ "${POST_CUSTOMER_VAULT_COUNT}" == "${PRE_CUSTOMER_VAULT_COUNT}" ]] || abort "DATA_INTEGRITY vaults changed"
[[ "${POST_ELIGIBILITY_RECORD_COUNT}" == "${PRE_ELIGIBILITY_RECORD_COUNT}" ]] || abort "DATA_INTEGRITY eligibility changed"
echo "DATA_INTEGRITY=PASS"
ROLLBACK_REQUIRED=NO

# Unset bound URL from environment for remaining steps (uvicorn loads .env from file)
unset DATABASE_URL DB_URL || true

# =====================================================================
checkpoint "J START SAAS 8010"
# =====================================================================
# Secrets gate
need_secrets=0
if ! grep -qE '^[[:space:]]*JWT_SECRET_KEY=[^[:space:]#]' "${ENV_FILE}"; then
  need_secrets=1
fi
if ! grep -qE '^[[:space:]]*VAULT_FERNET_KEY=[^[:space:]#]' "${ENV_FILE}"; then
  need_secrets=1
fi
if [[ "${need_secrets}" -eq 1 ]]; then
  USER_ACTION_REQUIRED=YES
  echo "USER_ACTION_REQUIRED=YES"
  echo "REASON=JWT_SECRET_KEY and/or VAULT_FERNET_KEY missing in .env (not invented by this script)"
  echo "HINT=Add secrets to ${ENV_FILE} (chmod 600), then: launchctl kickstart -k gui/\$(id -u)/${PLIST_LABEL}"
  abort "ENV secrets incomplete — migration DONE; backend start blocked (FAIL CLOSED)"
fi

# Ensure skip seed
grep -q 'GUOQIAO_SKIP_SEED=1' "${ENV_FILE}" || echo 'GUOQIAO_SKIP_SEED=1' >> "${ENV_FILE}"

bash "${GUARD}" "${BACKEND}" || abort "production-db-guard FAIL"

# Runtime env for LaunchAgent
mkdir -p "${STATE_DIR}/logs"
SAAS_PYTHON="${VENV_PY}"
if [[ ! -f "${RUNTIME_ENV}" ]]; then
  cat >"${RUNTIME_ENV}" <<EOF
SAAS_BACKEND_DIR=${BACKEND}
SAAS_PYTHON=${SAAS_PYTHON}
SAAS_VENV=${BACKEND}/.venv
SAAS_START_METHOD=launchd:${PLIST_LABEL}
EOF
fi
# Refresh python path
sed -i.bak "s|^SAAS_PYTHON=.*|SAAS_PYTHON=${SAAS_PYTHON}|" "${RUNTIME_ENV}" 2>/dev/null \
  || sed -i '' "s|^SAAS_PYTHON=.*|SAAS_PYTHON=${SAAS_PYTHON}|" "${RUNTIME_ENV}" 2>/dev/null || true

chmod +x "${RUN_WRAPPER}"
mkdir -p "${HOME}/Library/LaunchAgents"
if [[ ! -f "${PLIST_PATH}" ]]; then
  cat >"${PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>${RUN_WRAPPER}</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${BACKEND}</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${STATE_DIR}/logs/saas-backend.out.log</string>
  <key>StandardErrorPath</key>
  <string>${STATE_DIR}/logs/saas-backend.err.log</string>
</dict>
</plist>
EOF
fi

launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || launchctl unload "${PLIST_PATH}" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}" 2>/dev/null || launchctl load -w "${PLIST_PATH}"
launchctl kickstart -k "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true

ok8010=0
i=0
while [[ $i -lt 40 ]]; do
  i=$((i + 1))
  code="$(curl -sS -o /tmp/gq-h.json -w '%{http_code}' http://127.0.0.1:8010/api/health || echo 000)"
  if [[ "$code" == "200" ]]; then ok8010=1; break; fi
  sleep 1
done
[[ "${ok8010}" -eq 1 ]] || {
  tail -n 80 "${STATE_DIR}/logs/saas-backend.err.log" 2>/dev/null || true
  abort "8010 health not 200"
}

c_stu="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8010/api/students || echo 000)"
c_meta="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8010/api/students/meta || echo 000)"
c_uni="$(curl -sS -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8010/api/universities?target=international' || echo 000)"
c_sch="$(curl -sS -o /dev/null -w '%{http_code}' 'http://127.0.0.1:8010/api/schedules?target=international' || echo 000)"
echo "HEALTH_8010=200"
echo "STUDENTS_8010=${c_stu}"
echo "STUDENTS_META_8010=${c_meta}"
echo "UNIVERSITIES_8010=${c_uni}"
echo "SCHEDULES_8010=${c_sch}"
[[ "${c_stu}" == "401" || "${c_stu}" == "403" ]] || abort "students expected 401/403 got ${c_stu}"
[[ "${c_meta}" == "200" ]] || abort "students/meta expected 200 got ${c_meta}"
[[ "${c_uni}" == "200" ]] || abort "universities expected 200 got ${c_uni}"
[[ "${c_sch}" == "200" ]] || abort "schedules expected 200 got ${c_sch}"
echo "PORT_8010=UP"

# =====================================================================
checkpoint "K CADDY + go-live"
# =====================================================================
if [[ "${SKIP_GO_LIVE}" == "1" ]]; then
  echo "SKIP_GO_LIVE=1"
  CADDY_8088=SKIPPED
  TUNNEL_PERSISTENT=SKIPPED
else
  if bash "${ROOT}/deploy/api/m1-go-live.sh"; then
    caddy_h="$(curl -sS -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/health || echo 000)"
    echo "CADDY_HEALTH_HTTP=${caddy_h}"
    [[ "${caddy_h}" == "200" ]] || abort "Caddy health not 200"
    CADDY_8088=PASS
  else
    abort "m1-go-live.sh failed"
  fi
fi

# =====================================================================
checkpoint "L CLOUDFLARE TUNNEL"
# =====================================================================
TUNNEL_PERSISTENT=NO
if curl -fsS "https://api.guoqiaoplan.com/api/health" >/tmp/gq-pub.json 2>/dev/null; then
  echo "PUBLIC_HEALTH=200"
  # Named tunnel if cloudflared config exists
  if [[ -f "${HOME}/.cloudflared/guoqiao-api.yml" ]] || cloudflared tunnel list 2>/dev/null | grep -q guoqiao-api; then
    TUNNEL_PERSISTENT=YES
  else
    TUNNEL_PERSISTENT=UNKNOWN
    USER_ACTION_REQUIRED=YES
  fi
else
  echo "PUBLIC_HEALTH=NOT_OK"
  USER_ACTION_REQUIRED=YES
  TUNNEL_PERSISTENT=NO
  echo "HINT=Ensure named tunnel guoqiao-api routes api.guoqiaoplan.com -> 127.0.0.1:8088"
fi
echo "TUNNEL_PERSISTENT=${TUNNEL_PERSISTENT}"

# Secret scan of this process's key files (no .env dump)
if grep -RInE 'POSTGRES_PASSWORD=[^*]|postgresql\+psycopg://[^:]+:[^*@]+@' \
  /tmp/gq-pg-restore-list.txt /tmp/gq-h.json 2>/dev/null | grep -v '\*\*\*' | head -n 5; then
  abort "possible secret leak in temp logs"
fi

echo "============================================================"
echo "GUOQIAO_M1_PRODUCTION_DB_UPGRADE_SUMMARY"
echo "DATABASE_IDENTITY_CHECK=PASS"
echo "BACKUP_VERIFIED=YES"
echo "BACKUP_FILE=${BACKUP_FILE}"
echo "PRE_REVISION=${PRE_REVISION}"
echo "CURRENT_DB_REVISION=${POST_REV}"
echo "MIGRATION=PASS"
echo "SCHEMA_CURRENT=YES"
echo "DATA_INTEGRITY=PASS"
echo "DATABASE_URL_REDACTED=${DATABASE_URL_REDACTED}"
echo "STUDENT_MASTER_PROFILE_COUNT=${STUDENT_MASTER_PROFILE_COUNT}"
echo "STUDENT_TIMELINE_COUNT=${STUDENT_TIMELINE_COUNT}"
echo "PORT_8010=UP"
echo "CADDY_8088=${CADDY_8088:-UNKNOWN}"
echo "TUNNEL_PERSISTENT=${TUNNEL_PERSISTENT}"
echo "ROLLBACK_REQUIRED=${ROLLBACK_REQUIRED}"
echo "USER_ACTION_REQUIRED=${USER_ACTION_REQUIRED}"
echo "SEED_RUN=NO"
echo "SQLITE_FALLBACK=BLOCKED"
echo "CNBER_TOUCH=NO"
echo "============================================================"
exit 0
