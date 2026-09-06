#!/usr/bin/env bash
# M1 READ-ONLY schema fingerprint for confirmed candidate DB "huaqiao".
# Distinguishes DATABASE_IDENTITY vs SCHEMA_CURRENT (Student Profile V2 migrations).
#
# Absolute bans:
#   alembic upgrade/downgrade, INSERT/UPDATE/DELETE/DROP/ALTER/CREATE,
#   seed, stash pop, printing passwords / personal data / SELECT *
#
# Usage (M1):
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   bash deploy/api/m1-db-schema-fingerprint.sh
set -u
# NOT set -e — probe failures must not abort

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ALEMBIC_DIR="${BACKEND}/alembic/versions"
PG_CONTAINER="${PG_CONTAINER:-huaqiao-postgres}"
PG_DB="${PG_DB:-huaqiao}"
PG_HOST_PORT="${PG_HOST_PORT:-5433}"
EXPECTED_UNI=125
EXPECTED_TL=900

section() { echo; echo "======== $* ========"; }
warn() { echo "WARN: $*"; }
note() { echo "NOTE: $*"; }

redact_line() {
  echo "$1" | sed -E \
    -e 's#(://[^:/@]+:)[^@/]+@#\1***@#g' \
    -e 's#(POSTGRES_PASSWORD=)([^[:space:]]+)#\1***#g' \
    -e 's#(DATABASE_URL=)([^[:space:]]+)#\1REDACTED#g' \
    -e 's#(password[[:space:]]*=[[:space:]]*)[^[:space:]]+#\1***#gi'
}

echo "============================================================"
echo "GUOQIAO M1 DATABASE SCHEMA FINGERPRINT"
echo "READ_ONLY=YES"
echo "MIGRATION_RUN=NO"
echo "ROOT=${ROOT}"
echo "============================================================"

BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo UNKNOWN)"
HEAD="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo UNKNOWN)"
echo "BRANCH=${BRANCH}"
echo "HEAD=${HEAD}"

# ---------- Docker / user (password never printed) ----------
section "1 container identity"
PG_USER=""
CONTAINER_FOUND=NO
if command -v docker >/dev/null 2>&1 && docker inspect "${PG_CONTAINER}" >/dev/null 2>&1; then
  CONTAINER_FOUND=YES
  while IFS= read -r ev; do
    case "$ev" in
      POSTGRES_USER=*) PG_USER="${ev#POSTGRES_USER=}" ;;
      POSTGRES_DB=*)
        # prefer explicit PG_DB override; else container default
        if [[ "${PG_DB}" == "huaqiao" ]]; then
          :
        fi
        echo "CONTAINER_POSTGRES_DB=${ev#POSTGRES_DB=}"
        ;;
      POSTGRES_PASSWORD=*) echo "POSTGRES_PASSWORD=***" ;;
    esac
  done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${PG_CONTAINER}" 2>/dev/null || true)
  echo "CONTAINER_NAME=${PG_CONTAINER}"
  echo "IMAGE=$(docker inspect -f '{{.Config.Image}}' "${PG_CONTAINER}" 2>/dev/null || true)"
  echo "CREATED=$(docker inspect -f '{{.Created}}' "${PG_CONTAINER}" 2>/dev/null || true)"
  echo "RESTART_POLICY=$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "${PG_CONTAINER}" 2>/dev/null || true)"
  echo "MOUNTS=$(docker inspect -f '{{range .Mounts}}type={{.Type}} name={{.Name}} src={{.Source}} dst={{.Destination}}; {{end}}' "${PG_CONTAINER}" 2>/dev/null || true)"
else
  warn "container ${PG_CONTAINER} not found"
fi
PG_USER="${PG_USER:-huaqiao}"
echo "POSTGRES_USER=${PG_USER}"
echo "TARGET_DB=${PG_DB}"

pg_sql() {
  local sql="$1"
  docker exec "${PG_CONTAINER}" psql -U "${PG_USER}" -d "${PG_DB}" -v ON_ERROR_STOP=1 -tAc "$sql" 2>/dev/null
}

table_exists() {
  local t="$1"
  local r
  r="$(pg_sql "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='${t}' LIMIT 1;" || true)"
  [[ "$(echo "$r" | tr -d '[:space:]')" == "1" ]]
}

count_table() {
  local t="$1"
  if table_exists "$t"; then
    local c
    c="$(pg_sql "SELECT count(*) FROM ${t};" || echo NA)"
    echo "$(echo "$c" | tr -d '[:space:]')"
  else
    echo "ABSENT"
  fi
}

# ---------- Alembic revision in DB ----------
section "2 alembic_version (READ ONLY)"
CURRENT_DB_REVISION=UNKNOWN
if [[ "${CONTAINER_FOUND}" != "YES" ]]; then
  warn "skip SQL — no container"
else
  if table_exists alembic_version; then
    CURRENT_DB_REVISION="$(pg_sql "SELECT version_num FROM alembic_version ORDER BY version_num LIMIT 1;" || echo UNKNOWN)"
    CURRENT_DB_REVISION="$(echo "$CURRENT_DB_REVISION" | tr -d '[:space:]')"
    echo "CURRENT_DB_REVISION=${CURRENT_DB_REVISION}"
    # count rows (should be 1)
    echo "ALEMBIC_VERSION_ROWS=$(count_table alembic_version)"
  else
    CURRENT_DB_REVISION=MISSING_TABLE
    echo "CURRENT_DB_REVISION=MISSING_TABLE"
  fi
fi

# ---------- Repo migration map ----------
section "3 repository migration map (no alembic execute)"
EXPECTED_HEAD_REVISION=""
EXPECTED_STUDENT_MIGRATION="004_student_master_profile"
EXPECTED_TIMELINE_MIGRATION="005_student_timeline"
EXPECTED_SLOTS_MIGRATION="006_student_profile_slots"

echo "REPO_MIGRATIONS:"
if [[ -d "${ALEMBIC_DIR}" ]]; then
  for f in "${ALEMBIC_DIR}"/*.py; do
    [[ -f "$f" ]] || continue
    base="$(basename "$f")"
    rev="$(grep -E '^revision\s*=' "$f" | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/")"
    down="$(grep -E '^down_revision\s*=' "$f" | head -1 | sed -E "s/.*['\"]([^'\"]+)['\"].*/\1/; s/.*None.*/None/")"
    creates=""
    case "$base" in
      001_*) creates="tenants,users,auth_tokens,membership_plans,orders,payment_orders,recharge_codes,permission_configs,eligibility_records,universities,admission_schedules,customer_vaults,expert_consultations,..." ;;
      002_*) creates="ALTER eligibility_records,customer_vaults (privacy cols)" ;;
      003_*) creates="ALTER users.permissions, eligibility privacy cols" ;;
      004_*) creates="CREATE student_master_profiles" ;;
      005_*) creates="CREATE student_timeline_items" ;;
      006_*) creates="ALTER student_master_profiles status/archived/deleted; users.student_profile_limit_override" ;;
    esac
    echo "  FILE=${base} REVISION=${rev} DOWN_REVISION=${down} TABLES=${creates}"
    EXPECTED_HEAD_REVISION="$rev"
  done
else
  warn "alembic versions dir missing"
fi

# HEAD is last in lexical/chain — compute properly from 006
EXPECTED_HEAD_REVISION="006_student_profile_slots"
echo "EXPECTED_HEAD_REVISION=${EXPECTED_HEAD_REVISION}"
echo "EXPECTED_STUDENT_MIGRATION=${EXPECTED_STUDENT_MIGRATION} (creates student_master_profiles)"
echo "EXPECTED_TIMELINE_MIGRATION=${EXPECTED_TIMELINE_MIGRATION} (creates student_timeline_items)"
echo "EXPECTED_SLOTS_MIGRATION=${EXPECTED_SLOTS_MIGRATION}"

SCHEMA_CURRENT=NO
STUDENT_TABLE_PRESENT=NO
TIMELINE_TABLE_PRESENT=NO
REVISION_GAP=UNKNOWN

case "${CURRENT_DB_REVISION}" in
  006_student_profile_slots)
    SCHEMA_CURRENT=YES
    REVISION_GAP=NONE
    ;;
  005_student_timeline)
    SCHEMA_CURRENT=NO
    REVISION_GAP="needs 006_student_profile_slots"
    ;;
  004_student_master_profile)
    SCHEMA_CURRENT=NO
    REVISION_GAP="needs 005_student_timeline,006_student_profile_slots"
    ;;
  003_r43_fix)
    SCHEMA_CURRENT=NO
    REVISION_GAP="needs 004_student_master_profile,005_student_timeline,006_student_profile_slots"
    ;;
  002_privacy)
    SCHEMA_CURRENT=NO
    REVISION_GAP="needs 003..006"
    ;;
  001_initial)
    SCHEMA_CURRENT=NO
    REVISION_GAP="needs 002..006"
    ;;
  *)
    SCHEMA_CURRENT=NO
    REVISION_GAP="unknown_revision:${CURRENT_DB_REVISION}"
    ;;
esac

# ---------- Legacy student sources ----------
section "4 legacy student source counts (COUNT only — no PII)"
CUSTOMER_VAULT_COUNT=NA
USER_COUNT=NA
ELIGIBILITY_RECORD_COUNT=NA
STUDENT_MASTER_PROFILE_COUNT=NA
STUDENT_TIMELINE_COUNT=NA
UNI_COUNT=NA
TL_COUNT=NA
MEMBERSHIP_COUNT=NA

if [[ "${CONTAINER_FOUND}" == "YES" ]]; then
  CUSTOMER_VAULT_COUNT="$(count_table customer_vaults)"
  USER_COUNT="$(count_table users)"
  ELIGIBILITY_RECORD_COUNT="$(count_table eligibility_records)"
  STUDENT_MASTER_PROFILE_COUNT="$(count_table student_master_profiles)"
  STUDENT_TIMELINE_COUNT="$(count_table student_timeline_items)"
  UNI_COUNT="$(count_table universities)"
  TL_COUNT="$(count_table admission_schedules)"
  MEMBERSHIP_COUNT="$(count_table membership_plans)"

  if [[ "${STUDENT_MASTER_PROFILE_COUNT}" != "ABSENT" ]]; then
    STUDENT_TABLE_PRESENT=YES
  fi
  if [[ "${STUDENT_TIMELINE_COUNT}" != "ABSENT" ]]; then
    TIMELINE_TABLE_PRESENT=YES
  fi

  echo "CUSTOMER_VAULT_COUNT=${CUSTOMER_VAULT_COUNT}"
  echo "USER_COUNT=${USER_COUNT}"
  echo "ELIGIBILITY_RECORD_COUNT=${ELIGIBILITY_RECORD_COUNT}"
  echo "STUDENT_MASTER_PROFILE_COUNT=${STUDENT_MASTER_PROFILE_COUNT}"
  echo "STUDENT_TIMELINE_COUNT=${STUDENT_TIMELINE_COUNT}"
  echo "UNIVERSITY_COUNT=${UNI_COUNT}"
  echo "TIMELINE_COUNT=${TL_COUNT}"
  echo "MEMBERSHIP_COUNT=${MEMBERSHIP_COUNT}"

  # Column names only (no values)
  for t in customer_vaults users student_master_profiles student_timeline_items; do
    if table_exists "$t"; then
      echo "--- columns ${t} ---"
      pg_sql "SELECT column_name||':'||data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='${t}' ORDER BY ordinal_position;" \
        | sed '/^$/d' | sed 's/^/  /' || true
    else
      echo "--- columns ${t} --- ABSENT"
    fi
  done
fi

# Interpret historical "2 students"
HISTORICAL_STUDENT_SOURCE=UNKNOWN
note "Repo: pre-V2 student data lived in customer_vaults (001_initial); V2 table created only in 004_student_master_profile."
note "migrate_vault_if_needed() copies vault -> student_master_profiles after 004 exists."
if [[ "${STUDENT_TABLE_PRESENT}" == "NO" ]]; then
  if [[ "${CUSTOMER_VAULT_COUNT}" =~ ^[0-9]+$ ]] && [[ "${CUSTOMER_VAULT_COUNT}" -ge 1 ]]; then
    HISTORICAL_STUDENT_SOURCE="customer_vaults (legacy vault; count=${CUSTOMER_VAULT_COUNT})"
  elif [[ "${USER_COUNT}" == "2" ]]; then
    HISTORICAL_STUDENT_SOURCE="likely_users_count_mislabelled_as_students (USER_COUNT=2; seed admin+demo or two accounts)"
  else
    HISTORICAL_STUDENT_SOURCE="pre_V2_schema_without_student_master_profiles; check customer_vaults/users"
  fi
else
  HISTORICAL_STUDENT_SOURCE="student_master_profiles (V2)"
fi
echo "HISTORICAL_STUDENT_SOURCE=${HISTORICAL_STUDENT_SOURCE}"
echo "STUDENT_TABLE_PRESENT=${STUDENT_TABLE_PRESENT}"
echo "TIMELINE_TABLE_PRESENT=${TIMELINE_TABLE_PRESENT}"

# ---------- Identity decision (independent of V2 tables) ----------
section "5 DATABASE_IDENTITY vs SCHEMA_CURRENT"
DATABASE_IDENTITY_CONFIRMED=NO
uni_ok=0
tl_ok=0
users_ok=0
core_ok=0

if [[ "${UNI_COUNT}" == "${EXPECTED_UNI}" ]]; then uni_ok=1; fi
if [[ "${TL_COUNT}" == "${EXPECTED_TL}" ]]; then tl_ok=1; fi
if [[ "${USER_COUNT}" =~ ^[0-9]+$ ]] && [[ "${USER_COUNT}" -ge 1 ]]; then users_ok=1; fi
if table_exists universities && table_exists admission_schedules && table_exists users && table_exists membership_plans; then
  core_ok=1
fi

if [[ "${CONTAINER_FOUND}" == "YES" && "${PG_DB}" == "huaqiao" && "$uni_ok" -eq 1 && "$tl_ok" -eq 1 && "$users_ok" -eq 1 && "$core_ok" -eq 1 ]]; then
  DATABASE_IDENTITY_CONFIRMED=YES
fi

# Soft identity if counts slightly off but core+container match strongly
if [[ "${DATABASE_IDENTITY_CONFIRMED}" == "NO" && "${CONTAINER_FOUND}" == "YES" && "$core_ok" -eq 1 && "$users_ok" -eq 1 ]]; then
  if [[ "${UNI_COUNT}" =~ ^[0-9]+$ ]] && [[ "${UNI_COUNT}" -ge 100 ]] && [[ "${TL_COUNT}" =~ ^[0-9]+$ ]] && [[ "${TL_COUNT}" -ge 500 ]]; then
    DATABASE_IDENTITY_CONFIRMED=YES
    note "Soft identity: core SaaS tables + large catalog fingerprint (uni>=100, schedules>=500)"
  fi
fi

DATABASE_URL_REDACTED=""
if [[ "${DATABASE_IDENTITY_CONFIRMED}" == "YES" ]]; then
  # Driver form used by SaaS SQLAlchemy settings / docker-compose
  DATABASE_URL_REDACTED="postgresql+psycopg://${PG_USER}:***@127.0.0.1:${PG_HOST_PORT}/${PG_DB}"
fi

echo "DATABASE_IDENTITY_CONFIRMED=${DATABASE_IDENTITY_CONFIRMED}"
echo "SCHEMA_CURRENT=${SCHEMA_CURRENT}"
echo "STUDENT_TABLE_PRESENT=${STUDENT_TABLE_PRESENT}"
echo "REVISION_GAP=${REVISION_GAP}"
echo "DATABASE_URL_REDACTED=${DATABASE_URL_REDACTED}"
echo "IDENTITY_EVIDENCE_UNIVERSITIES=${UNI_COUNT}"
echo "IDENTITY_EVIDENCE_SCHEDULES=${TL_COUNT}"
echo "IDENTITY_EVIDENCE_USERS=${USER_COUNT}"

# ---------- Backup readiness (do NOT dump) ----------
section "6 backup readiness (no dump executed)"
PG_DUMP_AVAILABLE=NO
if command -v pg_dump >/dev/null 2>&1; then
  PG_DUMP_AVAILABLE=YES
elif docker exec "${PG_CONTAINER}" which pg_dump >/dev/null 2>&1; then
  PG_DUMP_AVAILABLE=YES_IN_CONTAINER
fi
echo "PG_DUMP_AVAILABLE=${PG_DUMP_AVAILABLE}"
echo "FUTURE_BACKUP_COMMAND_TEMPLATE="
echo "  # AFTER identity confirmed; BEFORE any migration — run manually later:"
echo "  # TS=\$(date +%Y%m%d_%H%M%S)"
echo "  # docker exec ${PG_CONTAINER} pg_dump -U ${PG_USER} -d ${PG_DB} -Fc -f /tmp/huaqiao_\${TS}.dump"
echo "  # docker cp ${PG_CONTAINER}:/tmp/huaqiao_\${TS}.dump ~/guoqiao-backups/"
echo "  # verify: non-zero file size; then and only then consider alembic upgrade"
echo "BACKUP_EXECUTED=NO"
echo "MIGRATION_RUN=NO"

# ---------- Repo code notes ----------
section "7 code notes (no DB write)"
echo "LEGACY_STUDENT_STORAGE=customer_vaults (created in 001_initial)"
echo "V2_STUDENT_STORAGE=student_master_profiles (created in 004_student_master_profile)"
echo "V2_TIMELINE_STORAGE=student_timeline_items (created in 005_student_timeline)"
echo "VAULT_MIGRATION_HELPER=app.student_api.migrate_vault_if_needed (runtime copy after table exists)"

section "SUMMARY"
cat <<SUM
READ_ONLY=YES
BRANCH=${BRANCH}
HEAD=${HEAD}
DATABASE_CANDIDATE=${PG_DB}
CURRENT_DB_REVISION=${CURRENT_DB_REVISION}
EXPECTED_HEAD_REVISION=${EXPECTED_HEAD_REVISION}
EXPECTED_STUDENT_MIGRATION=${EXPECTED_STUDENT_MIGRATION}
REVISION_GAP=${REVISION_GAP}
DATABASE_IDENTITY_CONFIRMED=${DATABASE_IDENTITY_CONFIRMED}
SCHEMA_CURRENT=${SCHEMA_CURRENT}
STUDENT_TABLE_PRESENT=${STUDENT_TABLE_PRESENT}
TIMELINE_TABLE_PRESENT=${TIMELINE_TABLE_PRESENT}
CUSTOMER_VAULT_COUNT=${CUSTOMER_VAULT_COUNT}
USER_COUNT=${USER_COUNT}
ELIGIBILITY_RECORD_COUNT=${ELIGIBILITY_RECORD_COUNT}
STUDENT_MASTER_PROFILE_COUNT=${STUDENT_MASTER_PROFILE_COUNT}
STUDENT_TIMELINE_COUNT=${STUDENT_TIMELINE_COUNT}
UNIVERSITY_COUNT=${UNI_COUNT}
TIMELINE_COUNT=${TL_COUNT}
HISTORICAL_STUDENT_SOURCE=${HISTORICAL_STUDENT_SOURCE}
DATABASE_URL_REDACTED=${DATABASE_URL_REDACTED}
PG_DUMP_AVAILABLE=${PG_DUMP_AVAILABLE}
BACKUP_EXECUTED=NO
MIGRATION_RUN=NO
SEED_RUN=NO
ENV_WRITE=NO
STASH_TOUCH=NO
CNBER_TOUCH=NO
DATABASE_CHANGED=NO
NEXT_STEP=Paste SUMMARY back. Do NOT migrate until backup plan approved. .env restore is a separate phase after IDENTITY=YES.
SUM

echo "============================================================"
echo "FINGERPRINT_COMPLETE"
echo "============================================================"
exit 0
