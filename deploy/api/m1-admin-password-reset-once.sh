#!/usr/bin/env bash
# M1 ONE-SHOT — reset the single production admin password (and optional name).
#
# Usage (on M1 only):
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   git pull origin cursor/mobile-cloud-preview
#   NEW_ADMIN_PASSWORD='…' NEW_ADMIN_NAME='管理员Admin' \
#     bash deploy/api/m1-admin-password-reset-once.sh
#
# Safety:
#   - Only updates users WHERE id=1 AND email=admin@example.com AND role=admin
#   - Uses app hash_password() (bcrypt) — never stores plaintext password in DB
#   - Does not print password / hash / DATABASE_URL secrets
#   - No seed, no sqlite, no CNBER, no tunnel/Caddy/secret regen, no auto pg_restore
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ENV_FILE="${BACKEND}/.env"
VENV_PY="${BACKEND}/.venv/bin/python"
PG_CONTAINER="huaqiao-postgres"
PG_DB="huaqiao"
PG_HOST="127.0.0.1"
PG_PORT="5433"
TARGET_ID=1
TARGET_EMAIL="admin@example.com"
TARGET_ROLE="admin"
SAAS_ADDR="127.0.0.1:8010"

abort() { echo "ABORT: $*" >&2; exit 1; }
info() { echo "==> $*"; }

[[ -n "${NEW_ADMIN_PASSWORD:-}" ]] || abort "set NEW_ADMIN_PASSWORD in the environment (do not commit it)"
[[ "${#NEW_ADMIN_PASSWORD}" -ge 8 ]] || abort "NEW_ADMIN_PASSWORD too short (<8)"
NEW_ADMIN_NAME="${NEW_ADMIN_NAME:-管理员Admin}"

[[ -x "${VENV_PY}" ]] || abort "missing ${VENV_PY}"
[[ -f "${ENV_FILE}" ]] || abort "missing ${ENV_FILE}"
docker inspect -f '{{.State.Running}}' "${PG_CONTAINER}" 2>/dev/null | grep -qx true \
  || abort "${PG_CONTAINER} not running"

_PG_USER=""; _PG_PASS=""; _PG_DBNAME=""
while IFS= read -r ev; do
  case "$ev" in
    POSTGRES_USER=*) _PG_USER="${ev#POSTGRES_USER=}" ;;
    POSTGRES_PASSWORD=*) _PG_PASS="${ev#POSTGRES_PASSWORD=}" ;;
    POSTGRES_DB=*) _PG_DBNAME="${ev#POSTGRES_DB=}" ;;
  esac
done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${PG_CONTAINER}")
[[ -n "${_PG_USER}" && -n "${_PG_PASS}" && "${_PG_DBNAME}" == "${PG_DB}" ]] \
  || abort "container postgres creds mismatch"

pg_sql() {
  docker exec -e PGPASSWORD="${_PG_PASS}" "${PG_CONTAINER}" \
    psql -U "${_PG_USER}" -d "${PG_DB}" -h localhost -p 5432 -v ON_ERROR_STOP=1 -Atc "$1"
}

# Precheck: exactly one matching admin row
ROW="$(pg_sql "SELECT id||'|'||email||'|'||coalesce(name,'')||'|'||role FROM users WHERE id=${TARGET_ID} AND email='${TARGET_EMAIL}' AND role='${TARGET_ROLE}';")"
[[ -n "${ROW}" ]] || abort "target admin row not found (id=${TARGET_ID} email=${TARGET_EMAIL} role=${TARGET_ROLE})"
ADMIN_COUNT="$(pg_sql "SELECT count(*) FROM users WHERE role='admin';" | tr -d '[:space:]')"
[[ "${ADMIN_COUNT}" == "1" ]] || abort "ADMIN_USER_COUNT=${ADMIN_COUNT} != 1 — refuse"
echo "TARGET_BEFORE=${ROW}"
echo "ADMIN_USER_COUNT=${ADMIN_COUNT}"

# Hash via application layer (never echo password / full hash)
HASH="$(
  cd "${BACKEND}" && \
  NEW_ADMIN_PASSWORD="${NEW_ADMIN_PASSWORD}" "${VENV_PY}" - <<'PY'
import os
from app.services.security import hash_password
pw = os.environ["NEW_ADMIN_PASSWORD"]
h = hash_password(pw)
assert h.startswith("$2b$") or h.startswith("$2a$")
print(h)
PY
)"
[[ -n "${HASH}" && "${HASH}" == \$2* ]] || abort "bcrypt hash generation failed"
echo "HASH_ALG=bcrypt"
echo "HASH_PREFIX=${HASH:0:7}***"

# Escape single quotes for SQL literal
HASH_SQL="${HASH//\'/\'\'}"
NAME_SQL="${NEW_ADMIN_NAME//\'/\'\'}"

info "UPDATE single admin row (password_hash + name)"
UPDATED="$(pg_sql "UPDATE users SET password_hash='${HASH_SQL}', name='${NAME_SQL}' WHERE id=${TARGET_ID} AND email='${TARGET_EMAIL}' AND role='${TARGET_ROLE}' RETURNING id||'|'||email||'|'||name||'|'||role;")"
[[ -n "${UPDATED}" ]] || abort "UPDATE returned no row — no change applied"
ROWS="$(pg_sql "SELECT count(*) FROM users WHERE id=${TARGET_ID} AND email='${TARGET_EMAIL}' AND role='${TARGET_ROLE}' AND name='${NAME_SQL}';" | tr -d '[:space:]')"
[[ "${ROWS}" == "1" ]] || abort "post-update verify failed"
echo "TARGET_AFTER=${UPDATED}"
echo "OTHER_USERS_TOUCHED=NO"
echo "PRODUCTION_PASSWORD_PLAINTEXT_STORED=NO"

# Verify login against local SaaS (do not print password)
info "verify login via ${SAAS_ADDR}"
CODE="$(
  curl -sS -o /tmp/gq-admin-login.json -w '%{http_code}' --connect-timeout 5 --max-time 20 \
    -X POST "http://${SAAS_ADDR}/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${TARGET_EMAIL}\",\"password\":$(python3 -c 'import json,os; print(json.dumps(os.environ["NEW_ADMIN_PASSWORD"]))')}" \
    || echo 000
)"
echo "LOGIN_HTTP=${CODE}"
[[ "${CODE}" == "200" ]] || abort "login verify failed HTTP=${CODE}"
python3 - <<'PY'
import json
d=json.load(open("/tmp/gq-admin-login.json"))
u=d.get("user") or {}
assert u.get("id")==1
assert u.get("email")=="admin@example.com"
assert u.get("role")=="admin"
print("LOGIN_USER_ID=%s" % u.get("id"))
print("LOGIN_EMAIL=%s" % u.get("email"))
print("LOGIN_NAME=%s" % u.get("name"))
print("LOGIN_ROLE=%s" % u.get("role"))
PY
rm -f /tmp/gq-admin-login.json

echo "ADMIN_PASSWORD_RESET=PASS"
echo "SECRET_WRITTEN_TO_GIT=NO"
echo "CNBER_CHANGED=NO"
echo "MAIN_CHANGED=NO"
echo "NEXT=Login at https://admin.guoqiaoplan.com with the new password; discard the old seed password"
