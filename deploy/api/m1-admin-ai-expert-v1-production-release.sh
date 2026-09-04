#!/usr/bin/env bash
# M1 PRODUCTION RELEASE — Admin + AI Expert Console V1 (Phase 5)
#
# Run ON M1 only:
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   git pull origin cursor/mobile-cloud-preview
#   bash deploy/api/m1-admin-ai-expert-v1-production-release.sh
#
# Does: backup → alembic 006→007 → integrity → kickstart SaaS → CORS admin origin
# Does NOT: main merge, CNber, tunnel recreate, Caddy route change, secret regen,
#           university/timeline mutation, student_id backfill, auto pg_restore
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ENV_FILE="${BACKEND}/.env"
STATE_DIR="${HOME}/.guoqiao/saas"
BACKUP_DIR="${HOME}/guoqiao-backups"
PG_CONTAINER="huaqiao-postgres"
PG_DB="huaqiao"
PG_HOST="127.0.0.1"
PG_PORT="5433"
EXPECTED_BEFORE="006_student_profile_slots"
EXPECTED_AFTER="007_admin_ai_expert_v1"
EXPECTED_UNI=125
EXPECTED_TL=900
EXPECTED_USERS=2
SAAS_LABEL="com.guoqiao.saas-backend"
CADDY_ADDR="127.0.0.1:8088"
SAAS_ADDR="127.0.0.1:8010"
ADMIN_ORIGIN="https://admin.guoqiaoplan.com"
APP_ORIGIN="https://app.guoqiaoplan.com"
API_ORIGIN="https://api.guoqiaoplan.com"

abort() { echo "ABORT: $*" >&2; echo "USER_ACTION_REQUIRED=YES"; exit 1; }
section() { echo; echo "######## $* ########"; }
info() { echo "==> $*"; }

http_code() {
  curl -sS -o /tmp/gq-p5-body.json -w '%{http_code}' --connect-timeout 5 --max-time 30 "$@" || echo "000"
}

pg_sql() {
  docker exec -i "${PG_CONTAINER}" psql -U postgres -d "${PG_DB}" -Atc "$1"
}

section "CHECKPOINT B — PRECHECK"
cd "${ROOT}"
git fetch origin cursor/mobile-cloud-preview
git checkout cursor/mobile-cloud-preview
git pull origin cursor/mobile-cloud-preview
test -f "${BACKEND}/alembic/versions/007_admin_ai_expert_v1.py" || abort "007 migration file missing after pull"

docker inspect -f '{{.State.Running}}' "${PG_CONTAINER}" 2>/dev/null | grep -qx true \
  || abort "huaqiao-postgres not running"

CUR_REV="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
echo "CURRENT_DB_REVISION=${CUR_REV}"
[[ "${CUR_REV}" == "${EXPECTED_BEFORE}" || "${CUR_REV}" == "${EXPECTED_AFTER}" ]] \
  || abort "unexpected alembic revision=${CUR_REV}"

UNI="$(pg_sql "SELECT count(*) FROM universities;" | tr -d '[:space:]')"
TL="$(pg_sql "SELECT count(*) FROM admission_schedules;" | tr -d '[:space:]')"
USERS="$(pg_sql "SELECT count(*) FROM users;" | tr -d '[:space:]')"
echo "universities=${UNI} admission_schedules=${TL} users=${USERS}"
[[ "${UNI}" == "${EXPECTED_UNI}" ]] || abort "universities != ${EXPECTED_UNI}"
[[ "${TL}" == "${EXPECTED_TL}" ]] || abort "admission_schedules != ${EXPECTED_TL}"
[[ "${USERS}" == "${EXPECTED_USERS}" ]] || abort "users != ${EXPECTED_USERS}"

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

# Confirm DATABASE_URL targets production 5433/huaqiao (never print full URL)
python3 - <<'PY' "${ENV_FILE}" || abort "DATABASE_URL target check failed"
import sys
from pathlib import Path
p=Path(sys.argv[1])
url=""
for line in p.read_text().splitlines():
    if line.strip().startswith("DATABASE_URL="):
        url=line.split("=",1)[1].strip().strip('"').strip("'")
ok = ("127.0.0.1:5433/huaqiao" in url) or ("localhost:5433/huaqiao" in url)
print("DATABASE_URL_TARGET_OK=", "YES" if ok else "NO")
raise SystemExit(0 if ok else 1)
PY

PLANS_BEFORE="$(pg_sql "SELECT count(*) FROM membership_plans;" | tr -d '[:space:]')"
EC_BEFORE="$(pg_sql "SELECT count(*) FROM expert_consultations;" | tr -d '[:space:]')"
ER_BEFORE="$(pg_sql "SELECT count(*) FROM eligibility_records;" | tr -d '[:space:]')"

if [[ "${CUR_REV}" == "${EXPECTED_AFTER}" ]]; then
  info "Already at 007 — skip migrate (idempotent continue)"
  SKIP_MIGRATE=YES
else
  SKIP_MIGRATE=NO
fi

section "CHECKPOINT C — BACKUP"
mkdir -p "${BACKUP_DIR}"
TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/huaqiao_pre_007_${TS}.dump"
docker exec "${PG_CONTAINER}" pg_dump -U postgres -Fc "${PG_DB}" > "${BACKUP_FILE}"
[[ -s "${BACKUP_FILE}" ]] || abort "backup empty"
pg_restore -l "${BACKUP_FILE}" >/tmp/gq-p5-restore.list
[[ -s /tmp/gq-p5-restore.list ]] || abort "pg_restore -l failed"
echo "BACKUP_FILE=${BACKUP_FILE}"
echo "BACKUP_SIZE=$(wc -c < "${BACKUP_FILE}" | tr -d ' ')"
echo "BACKUP_VERIFIED=YES"

if [[ "${SKIP_MIGRATE}" != "YES" ]]; then
  section "CHECKPOINT D — APPLY 007"
  cd "${BACKEND}"
  # Use production .env via pydantic / alembic DATABASE_URL
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
  export DATABASE_URL
  # Refuse wrong target again
  case "${DATABASE_URL}" in
    *":5433/"*"huaqiao"*) ;;
    *) abort "DATABASE_URL not production 5433/huaqiao" ;;
  esac
  BEFORE="$(python3 -m alembic current 2>/dev/null | tail -1 | awk '{print $1}')"
  echo "ALEMBIC_CURRENT_BEFORE=${BEFORE}"
  [[ "${BEFORE}" == "${EXPECTED_BEFORE}" ]] || abort "alembic current != 006 before upgrade"
  HEADS="$(python3 -m alembic heads 2>/dev/null | awk '{print $1}')"
  echo "ALEMBIC_HEADS=${HEADS}"
  echo "${HEADS}" | grep -qx "${EXPECTED_AFTER}" || abort "alembic heads != 007"
  python3 -m alembic upgrade head
  AFTER="$(python3 -m alembic current 2>/dev/null | tail -1 | awk '{print $1}')"
  echo "DB_REVISION_AFTER=${AFTER}"
  [[ "${AFTER}" == "${EXPECTED_AFTER}" ]] || abort "upgrade did not land on 007"
  echo "MIGRATION=PASS"
else
  echo "MIGRATION=SKIPPED_ALREADY_007"
fi

section "CHECKPOINT E — SCHEMA VERIFY"
python3 - <<'PY'
import os, sys
from sqlalchemy import create_engine, inspect, text
url=os.environ.get("DATABASE_URL")
if not url:
    # reload from .env
    from pathlib import Path
    for line in Path(os.path.expanduser("/Users/agent001/deploy/huaqiao-international-eligibility-system/huaqiao-saas-pro/backend/.env")).read_text().splitlines():
        if line.startswith("DATABASE_URL="):
            url=line.split("=",1)[1].strip().strip('"').strip("'")
e=create_engine(url)
insp=inspect(e)
ec={c['name'] for c in insp.get_columns('expert_consultations')}
er={c['name'] for c in insp.get_columns('eligibility_records')}
need_ec={'student_id','assigned_consultant_id','ai_provider','ai_model','report_kind','status'}
miss=need_ec-ec
if miss:
    print("MISSING_EC", miss); sys.exit(1)
if 'student_id' not in er:
    print("MISSING_ER student_id"); sys.exit(1)
if 'audit_events' not in insp.get_table_names():
    print("MISSING audit_events"); sys.exit(1)
print("SCHEMA_VERIFY=PASS")
print("NOTE: provider column name=ai_provider; model column name=ai_model (existing)")
PY

section "CHECKPOINT F — DATA INTEGRITY"
UNI2="$(pg_sql "SELECT count(*) FROM universities;" | tr -d '[:space:]')"
TL2="$(pg_sql "SELECT count(*) FROM admission_schedules;" | tr -d '[:space:]')"
USERS2="$(pg_sql "SELECT count(*) FROM users;" | tr -d '[:space:]')"
PLANS2="$(pg_sql "SELECT count(*) FROM membership_plans;" | tr -d '[:space:]')"
EC2="$(pg_sql "SELECT count(*) FROM expert_consultations;" | tr -d '[:space:]')"
ER2="$(pg_sql "SELECT count(*) FROM eligibility_records;" | tr -d '[:space:]')"
echo "universities=${UNI2} timelines=${TL2} users=${USERS2} plans=${PLANS2} expert=${EC2} eligibility=${ER2}"
[[ "${UNI2}" == "${EXPECTED_UNI}" && "${TL2}" == "${EXPECTED_TL}" && "${USERS2}" == "${EXPECTED_USERS}" ]] \
  || abort "core counts drifted"
[[ "${PLANS2}" == "${PLANS_BEFORE}" ]] || abort "membership_plans count changed"
[[ "${EC2}" == "${EC_BEFORE}" ]] || abort "expert_consultations count changed"
[[ "${ER2}" == "${ER_BEFORE}" ]] || abort "eligibility_records count changed"
echo "DATA_INTEGRITY=PASS"

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

# Auth probes (seed credentials may not exist in production — informational only)
ADMIN_LOGIN_CODE="$(http_code -X POST "http://${SAAS_ADDR}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@example.com","password":"admin123456"}')"
echo "SEED_ADMIN_LOGIN_HTTP=${ADMIN_LOGIN_CODE}"

# Check if any production user has role=admin
ADMIN_COUNT="$(pg_sql "SELECT count(*) FROM users WHERE role='admin';" | tr -d '[:space:]')"
echo "ADMIN_USER_COUNT=${ADMIN_COUNT}"
if [[ "${ADMIN_COUNT}" == "0" ]]; then
  echo "USER_ACTION_REQUIRED=YES"
  echo "USER_ACTION=No users.role=admin in production. Do NOT silent SQL. Propose promote via controlled op after owner confirms email."
  pg_sql "SELECT id,email,role,plan_code FROM users ORDER BY id;"
fi

section "CHECKPOINT SUMMARY (M1)"
REV_NOW="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
echo "DB_REVISION_AFTER=${REV_NOW}"
echo "BACKUP_FILE=${BACKUP_FILE}"
echo "BACKUP_VERIFIED=YES"
echo "DATA_INTEGRITY=PASS"
echo "UNIVERSITY_COUNT=${UNI2}"
echo "TIMELINE_COUNT=${TL2}"
echo "USER_COUNT=${USERS2}"
echo "SAAS_8010=UP"
echo "ADMIN_API=MOUNTED"
echo "TUNNEL_CHANGED=NO"
echo "CADDY_CHANGED=NO"
echo "SECRET_CHANGED=NO"
echo "CNBER_CHANGED=NO"
echo "MAIN_CHANGED=NO"
echo "ADMIN_URL=https://admin.guoqiaoplan.com"
echo "PRODUCTION_FREEZE=NO"
echo "NEXT=Admin login E2E (dashboard/users/students/Student360 + AI Draft→Publish) then H5 published-only; freeze only if all PASS"
