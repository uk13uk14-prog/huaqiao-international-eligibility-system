#!/usr/bin/env bash
# M1 READ-ONLY production database source discovery.
# DISCOVERY_ONLY=YES — never writes .env, never starts backend, never mutates DB.
#
# Absolute bans in this script:
#   INSERT UPDATE DELETE DROP ALTER CREATE DATABASE CREATE TABLE
#   alembic upgrade/downgrade seed init_db create_all stash pop/apply/drop
#   printing full DATABASE_URL / passwords / tokens
#
# Usage (M1):
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   bash deploy/api/m1-db-source-discover.sh
set -u
# Intentionally NOT set -e: individual probe failures must not abort discovery.

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
DISCOVERY_ONLY=YES
EXPECTED_UNI=125
EXPECTED_TL=900
EXPECTED_STU=2
PG_CONTAINER_DEFAULT=huaqiao-postgres
PG_HOST_PORT_DEFAULT=5433

section() { echo; echo "======== $* ========"; }
ok() { echo "OK: $*"; }
warn() { echo "WARN: $*"; }
note() { echo "NOTE: $*"; }
fail_item() { echo "FAIL_ITEM: $*"; }

# Redact passwords in URLs and key=value lines
redact_line() {
  echo "$1" | sed -E \
    -e 's#(://[^:/@]+:)[^@/]+@#\1***@#g' \
    -e 's#(DATABASE_URL=)([^[:space:]]+)#\1REDACTED#g' \
    -e 's#(POSTGRES_PASSWORD=)([^[:space:]]+)#\1***#g' \
    -e 's#(JWT_SECRET_KEY=)([^[:space:]]+)#\1***#g' \
    -e 's#(VAULT_FERNET_KEY=)([^[:space:]]+)#\1***#g' \
    -e 's#(ADMIN_TOKEN=)([^[:space:]]+)#\1***#g' \
    -e 's#(password[[:space:]]*=[[:space:]]*)[^[:space:]]+#\1***#gi' \
    -e 's#(PASSWORD[[:space:]]*=[[:space:]]*)[^[:space:]]+#\1***#gi'
}

safe_cmd() {
  # run command; capture status; never abort script
  "$@"
  return 0
}

echo "============================================================"
echo "GUOQIAO M1 DATABASE SOURCE DISCOVERY"
echo "DISCOVERY_ONLY=${DISCOVERY_ONLY}"
echo "ROOT=${ROOT}"
echo "BACKEND=${BACKEND}"
echo "READ_ONLY_SQL_ONLY=YES"
echo "============================================================"

# ---------- 1. Git ----------
section "1 git identity"
BRANCH="$(git -C "$ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo UNKNOWN)"
HEAD="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo UNKNOWN)"
echo "BRANCH=${BRANCH}"
echo "HEAD=${HEAD}"
git -C "$ROOT" status -sb 2>/dev/null || warn "git status failed"

section "1b git stash list (read-only; no pop/apply/drop)"
if git -C "$ROOT" stash list 2>/dev/null | head -n 50; then
  STASH_COUNT="$(git -C "$ROOT" stash list 2>/dev/null | wc -l | tr -d ' ')"
  echo "STASH_COUNT=${STASH_COUNT}"
  # show metadata only for first few
  i=0
  while IFS= read -r sref; do
    [[ -n "$sref" ]] || continue
    i=$((i + 1))
    [[ $i -le 5 ]] || break
    echo "--- stash show ${sref} (stat) ---"
    git -C "$ROOT" stash show --stat "$sref" 2>/dev/null | head -n 40 || true
  done < <(git -C "$ROOT" stash list --format='%gd' 2>/dev/null || true)
else
  warn "stash list unavailable"
fi
echo "STASH_TOUCH=NO"

# ---------- 2. Backend files ----------
section "2 backend env / requirements / config"
for f in \
  "${BACKEND}/.env" \
  "${BACKEND}/.env.local" \
  "${BACKEND}/.env.production" \
  "${BACKEND}/.env.example" \
  "${BACKEND}/requirements.txt" \
  "${BACKEND}/requirements-locked.txt" \
  "${BACKEND}/pyproject.toml" \
  "${BACKEND}/app/config.py" \
  "${BACKEND}/app/database.py" \
  "${BACKEND}/app/models.py"
do
  if [[ -e "$f" ]]; then
    echo "PRESENT $(echo "$f" | sed "s#^${ROOT}/##")"
  else
    echo "ABSENT  $(echo "$f" | sed "s#^${ROOT}/##")"
  fi
done

# list .env* without dumping secrets
echo "--- backend .env* names ---"
ls -la "${BACKEND}"/.env* 2>/dev/null | awk '{print $NF}' || echo "(none)"

echo "--- sqlite / db files in backend (names only) ---"
found_db=0
for f in "${BACKEND}"/*.db "${BACKEND}"/*.sqlite "${BACKEND}"/*.sqlite3; do
  [[ -e "$f" ]] || continue
  found_db=1
  sz="$(wc -c < "$f" 2>/dev/null | tr -d ' ' || echo 0)"
  echo "DB_FILE name=$(basename "$f") bytes=${sz}"
done
[[ "$found_db" -eq 1 ]] || echo "DB_FILE none"

echo "--- ORM __tablename__ (from models.py) ---"
if [[ -f "${BACKEND}/app/models.py" ]]; then
  grep -E '__tablename__\s*=' "${BACKEND}/app/models.py" | sed 's/^[[:space:]]*//' || true
fi

echo "--- config database_url default (source line, no secrets) ---"
if [[ -f "${BACKEND}/app/config.py" ]]; then
  grep -n 'database_url\|DATABASE_URL\|env_file\|sqlite' "${BACKEND}/app/config.py" | head -n 20 || true
fi

# Catalog vs DB source hints
UNI_JSON=UNKNOWN
TL_JSON=UNKNOWN
if [[ -f "${BACKEND}/app/services/university_catalog.py" ]]; then
  UNI_JSON=CODE_CATALOG
fi
if [[ -f "${BACKEND}/app/services/data_baseline.py" ]]; then
  note "data_baseline: historical UNIVERSITY_COUNT=125 seeded DB; AdmissionSchedule~900 after seed; JSON catalog also exists"
  UNI_SOURCE_HINT=DB_OR_MIXED_WITH_JSON_CATALOG
  TL_SOURCE_HINT=DB_admission_schedules_OR_CODE_TEMPLATES
else
  UNI_SOURCE_HINT=UNKNOWN
  TL_SOURCE_HINT=UNKNOWN
fi
echo "UNIVERSITY_SOURCE_HINT=${UNI_SOURCE_HINT}"
echo "TIMELINE_SOURCE_HINT=${TL_SOURCE_HINT}"
echo "STUDENT_SOURCE_HINT=DB:student_master_profiles"

# ---------- 3. Shell profiles ----------
section "3 shell profiles (redacted matches only)"
for f in \
  "${HOME}/.zshrc" "${HOME}/.zprofile" "${HOME}/.profile" \
  "${HOME}/.bash_profile" "${HOME}/.bashrc"
do
  if [[ ! -f "$f" ]]; then
    echo "ABSENT $f"
    continue
  fi
  echo "PRESENT $f"
  grep -nE 'DATABASE_URL|POSTGRES|5433|huaqiao-saas|8010|uvicorn' "$f" 2>/dev/null | while IFS= read -r line; do
    redact_line "$line"
  done || true
done

# ---------- 4. History ----------
section "4 shell history (redacted)"
for hist in "${HOME}/.zsh_history" "${HOME}/.bash_history" "${HOME}/.history"; do
  if [[ ! -f "$hist" ]]; then
    echo "ABSENT $hist"
    continue
  fi
  echo "PRESENT $hist"
  grep -E 'DATABASE_URL|uvicorn|8010|huaqiao-saas-pro|postgres|5433|huaqiao-postgres' "$hist" 2>/dev/null | tail -n 40 | while IFS= read -r line; do
    redact_line "$line"
  done || true
done

# ---------- 5. LaunchAgents / Daemons ----------
section "5 LaunchAgents"
if [[ -d "${HOME}/Library/LaunchAgents" ]]; then
  ls -la "${HOME}/Library/LaunchAgents" 2>/dev/null | head -n 80 || true
  for f in "${HOME}/Library/LaunchAgents"/*guoqiao* \
           "${HOME}/Library/LaunchAgents"/*huaqiao* \
           "${HOME}/Library/LaunchAgents"/*saas*; do
    [[ -e "$f" ]] || continue
    echo "--- plist $f ---"
    if command -v plutil >/dev/null 2>&1; then
      plutil -p "$f" 2>/dev/null | while IFS= read -r line; do redact_line "$line"; done || true
    else
      grep -E 'Program|WorkingDirectory|Label|DATABASE|PORT|8010|5433' "$f" 2>/dev/null | while IFS= read -r line; do redact_line "$line"; done || true
    fi
  done
else
  echo "LaunchAgents dir ABSENT (not macOS?)"
fi

section "5b LaunchDaemons"
if [[ -d /Library/LaunchDaemons ]]; then
  if ls /Library/LaunchDaemons 2>/dev/null | head -n 5 >/dev/null; then
    ls /Library/LaunchDaemons 2>/dev/null | grep -Ei 'guoqiao|huaqiao|saas|postgres' || echo "(no matching daemon names)"
  else
    echo "LaunchDaemons=SKIPPED (no permission)"
  fi
else
  echo "LaunchDaemons=SKIPPED (dir missing)"
fi

# ---------- 6. Docker ----------
section "6 docker ps -a"
if command -v docker >/dev/null 2>&1; then
  docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}' 2>/dev/null || warn "docker ps failed"
else
  warn "docker not installed"
fi

section "6b docker inspect ${PG_CONTAINER_DEFAULT}"
PG_USER=""
PG_DB=""
PG_IMAGE=""
PG_CREATED=""
PG_RESTART=""
PG_MOUNTS=""
PG_PORTS=""
CONTAINER_FOUND=NO
if command -v docker >/dev/null 2>&1 && docker inspect "${PG_CONTAINER_DEFAULT}" >/dev/null 2>&1; then
  CONTAINER_FOUND=YES
  PG_IMAGE="$(docker inspect -f '{{.Config.Image}}' "${PG_CONTAINER_DEFAULT}" 2>/dev/null || true)"
  PG_CREATED="$(docker inspect -f '{{.Created}}' "${PG_CONTAINER_DEFAULT}" 2>/dev/null || true)"
  PG_RESTART="$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "${PG_CONTAINER_DEFAULT}" 2>/dev/null || true)"
  PG_PORTS="$(docker inspect -f '{{json .NetworkSettings.Ports}}' "${PG_CONTAINER_DEFAULT}" 2>/dev/null || true)"
  PG_MOUNTS="$(docker inspect -f '{{range .Mounts}}type={{.Type}} src={{.Source}} dst={{.Destination}}; {{end}}' "${PG_CONTAINER_DEFAULT}" 2>/dev/null || true)"
  # Env: extract user/db only — never print password
  while IFS= read -r ev; do
    case "$ev" in
      POSTGRES_USER=*) PG_USER="${ev#POSTGRES_USER=}" ;;
      POSTGRES_DB=*) PG_DB="${ev#POSTGRES_DB=}" ;;
      POSTGRES_PASSWORD=*) echo "POSTGRES_PASSWORD=***" ;;
      POSTGRES_HOST_AUTH_METHOD=*) echo "$ev" ;;
    esac
  done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${PG_CONTAINER_DEFAULT}" 2>/dev/null || true)

  echo "CONTAINER_NAME=${PG_CONTAINER_DEFAULT}"
  echo "CONTAINER_FOUND=YES"
  echo "IMAGE=${PG_IMAGE}"
  echo "CREATED=${PG_CREATED}"
  echo "RESTART_POLICY=${PG_RESTART}"
  echo "PORTS_JSON=${PG_PORTS}"
  echo "MOUNTS=${PG_MOUNTS}"
  echo "POSTGRES_USER=${PG_USER:-UNKNOWN}"
  echo "POSTGRES_DB=${PG_DB:-UNKNOWN}"
else
  echo "CONTAINER_FOUND=NO"
  warn "container ${PG_CONTAINER_DEFAULT} not inspectable"
fi

section "6c docker compose files in repo"
while IFS= read -r cf; do
  echo "COMPOSE_FILE=${cf#"$ROOT"/}"
  # print non-secret lines mentioning postgres / ports / saas
  grep -nE 'postgres|5432|5433|8010|DATABASE|huaqiao|saas' "$cf" 2>/dev/null | while IFS= read -r line; do
    redact_line "$line"
  done || true
done < <(find "$ROOT" -maxdepth 4 \( -name 'docker-compose.yml' -o -name 'docker-compose.yaml' -o -name 'compose.yml' -o -name 'compose.yaml' \) 2>/dev/null | head -n 20)

# ---------- 7. Host port 5433 ----------
section "7 host listen 127.0.0.1:5433"
PORT_5433=DOWN
if command -v lsof >/dev/null 2>&1; then
  if lsof -nP -iTCP:5433 -sTCP:LISTEN 2>/dev/null | head -n 5; then
    PORT_5433=UP
  else
    echo "(lsof: nothing on 5433)"
  fi
elif command -v nc >/dev/null 2>&1; then
  if nc -z 127.0.0.1 5433 2>/dev/null; then
    PORT_5433=UP
    echo "nc: 5433 accept"
  else
    echo "nc: 5433 refused"
  fi
else
  warn "no lsof/nc to probe 5433"
fi
echo "POSTGRES_HOST_PORT_5433=${PORT_5433}"

# ---------- 8. git ignored ----------
section "8 git ignored / check-ignore"
git -C "$ROOT" status --ignored -uall 2>/dev/null | grep -E '\.env|saas_pro|\.db|sqlite' | head -n 40 || echo "(no matching ignored lines)"
for p in \
  "huaqiao-saas-pro/backend/.env" \
  "huaqiao-saas-pro/backend/.env.local" \
  "huaqiao-saas-pro/backend/saas_pro.db" \
  ".env"
do
  if git -C "$ROOT" check-ignore -v "$p" 2>/dev/null; then
    :
  else
    echo "check-ignore: ${p} -> not ignored or missing"
  fi
done

# ---------- 9. git history (redacted) ----------
section "9 git log/grep history (redacted)"
git -C "$ROOT" log -n 30 --oneline --all --grep='postgres\|5433\|DATABASE\|huaqiao-postgres\|8010' -i 2>/dev/null | head -n 30 || true
# pickaxe search limited
git -C "$ROOT" log -n 20 -S'DATABASE_URL' --oneline -- '**/.env*' '**/docker-compose*' '**/README*' 'deploy/**' 2>/dev/null | head -n 20 || true
git -C "$ROOT" log -n 10 -S'5433' --oneline -- deploy 2>/dev/null | head -n 10 || true

# ---------- 10. deploy docs ----------
section "10 deploy docs mentions"
grep -RInE '8010|5433|huaqiao-postgres|DATABASE_URL|saas_pro\.db' \
  "${ROOT}/deploy" "${ROOT}/README.md" "${ROOT}/huaqiao-saas-pro/README.md" \
  2>/dev/null | while IFS= read -r line; do redact_line "$line"; done | head -n 80 || true

# ---------- 11. ORM mapping table ----------
section "11 ORM model → table mapping"
cat <<'ORM'
ORM_MODEL=Tenant                    TABLE=tenants
ORM_MODEL=User                      TABLE=users
ORM_MODEL=AuthToken                 TABLE=auth_tokens
ORM_MODEL=MembershipPlan            TABLE=membership_plans
ORM_MODEL=Order                     TABLE=orders
ORM_MODEL=PaymentOrder              TABLE=payment_orders
ORM_MODEL=RechargeCode              TABLE=recharge_codes
ORM_MODEL=PermissionConfig          TABLE=permission_configs
ORM_MODEL=EligibilityRecord         TABLE=eligibility_records
ORM_MODEL=University                TABLE=universities
ORM_MODEL=AdmissionSchedule         TABLE=admission_schedules
ORM_MODEL=CustomerVault             TABLE=customer_vaults
ORM_MODEL=StudentMasterProfile      TABLE=student_master_profiles
ORM_MODEL=StudentTimelineItem       TABLE=student_timeline_items
ORM_MODEL=ExpertConsultation        TABLE=expert_consultations
ORM_MODEL=ConsultationReportVersion TABLE=consultation_report_versions
ORM_MODEL=MemberTimelineReminder    TABLE=member_timeline_reminders
EXPECTED_FINGERPRINT universities≈125 admission_schedules≈900 student_master_profiles≈2
NOTE: universities/schedules may also exist in code catalog (MIXED); students are DB-only.
ORM

# ---------- 12. READ-ONLY Postgres probe ----------
section "12 READ-ONLY postgres fingerprint (docker exec)"
DATABASE_SOURCE_CONFIRMED=NO
DATABASE_URL_REDACTED=""
SCHEMA_MATCH=NO
UNI_COUNT=NA
TL_COUNT=NA
STU_COUNT=NA
USER_COUNT=NA
RECORD_COUNT=NA
MEMBERSHIP_COUNT=NA
CANDIDATE_DBS=""
UNIVERSITY_SOURCE=UNKNOWN
TIMELINE_SOURCE=UNKNOWN
STUDENT_SOURCE=DB

pg_exec_sql() {
  # $1=db $2=sql — SELECT only; caller responsibility
  local db="$1"
  local sql="$2"
  local user="${PG_USER:-postgres}"
  docker exec "${PG_CONTAINER_DEFAULT}" psql -U "$user" -d "$db" -v ON_ERROR_STOP=1 -tAc "$sql" 2>/dev/null
}

if [[ "${CONTAINER_FOUND}" == "YES" ]]; then
  user="${PG_USER:-postgres}"
  echo "Using docker exec psql -U ${user} (password not required from host)"
  DBS="$(pg_exec_sql postgres "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname;" || true)"
  if [[ -z "${DBS}" ]]; then
    warn "could not list databases via docker exec"
  else
    echo "--- databases ---"
    echo "$DBS"
    CANDIDATE_DBS="$(echo "$DBS" | tr '\n' ' ')"
  fi

  # Probe each non-template DB for ORM tables + counts
  best_score=-1
  best_db=""
  while IFS= read -r dbname; do
    [[ -n "$dbname" ]] || continue
    [[ "$dbname" == "postgres" ]] && continue
    echo "--- probe database: ${dbname} ---"
    tables="$(pg_exec_sql "$dbname" "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;" || true)"
    if [[ -z "$tables" ]]; then
      echo "tables: (none or error)"
      continue
    fi
    echo "tables:"
    echo "$tables" | sed 's/^/  /'

    has_uni=0; has_sched=0; has_stu=0; has_users=0; has_elig=0; has_plans=0
    echo "$tables" | grep -qx 'universities' && has_uni=1
    echo "$tables" | grep -qx 'admission_schedules' && has_sched=1
    echo "$tables" | grep -qx 'student_master_profiles' && has_stu=1
    echo "$tables" | grep -qx 'users' && has_users=1
    echo "$tables" | grep -qx 'eligibility_records' && has_elig=1
    echo "$tables" | grep -qx 'membership_plans' && has_plans=1

    score=$((has_uni + has_sched + has_stu + has_users + has_elig + has_plans))
    echo "ORM_TABLE_HITS=${score}/6"

    uc=NA; tc=NA; sc=NA; usc=NA; rc=NA; mc=NA
    if [[ "$has_uni" -eq 1 ]]; then
      uc="$(pg_exec_sql "$dbname" "SELECT count(*) FROM universities;" || echo NA)"
      uc="$(echo "$uc" | tr -d '[:space:]')"
    fi
    if [[ "$has_sched" -eq 1 ]]; then
      tc="$(pg_exec_sql "$dbname" "SELECT count(*) FROM admission_schedules;" || echo NA)"
      tc="$(echo "$tc" | tr -d '[:space:]')"
    fi
    if [[ "$has_stu" -eq 1 ]]; then
      sc="$(pg_exec_sql "$dbname" "SELECT count(*) FROM student_master_profiles;" || echo NA)"
      sc="$(echo "$sc" | tr -d '[:space:]')"
    fi
    if [[ "$has_users" -eq 1 ]]; then
      usc="$(pg_exec_sql "$dbname" "SELECT count(*) FROM users;" || echo NA)"
      usc="$(echo "$usc" | tr -d '[:space:]')"
    fi
    if [[ "$has_elig" -eq 1 ]]; then
      rc="$(pg_exec_sql "$dbname" "SELECT count(*) FROM eligibility_records;" || echo NA)"
      rc="$(echo "$rc" | tr -d '[:space:]')"
    fi
    if [[ "$has_plans" -eq 1 ]]; then
      mc="$(pg_exec_sql "$dbname" "SELECT count(*) FROM membership_plans;" || echo NA)"
      mc="$(echo "$mc" | tr -d '[:space:]')"
    fi
    echo "FINGERPRINT db=${dbname} universities=${uc} admission_schedules=${tc} student_master_profiles=${sc} users=${usc} eligibility_records=${rc} membership_plans=${mc}"

    if [[ "$score" -gt "$best_score" ]]; then
      best_score=$score
      best_db="$dbname"
      UNI_COUNT="$uc"
      TL_COUNT="$tc"
      STU_COUNT="$sc"
      USER_COUNT="$usc"
      RECORD_COUNT="$rc"
      MEMBERSHIP_COUNT="$mc"
    fi
  done <<< "$(echo "$DBS")"

  if [[ -n "$best_db" && "$best_score" -ge 4 ]]; then
    SCHEMA_MATCH=YES
    echo "BEST_CANDIDATE_DB=${best_db}"
    echo "SCHEMA_MATCH=YES"
    # Confirm fingerprint: students especially; uni/tl soft match
    stu_ok=0
    if [[ "${STU_COUNT}" =~ ^[0-9]+$ ]] && [[ "${STU_COUNT}" -ge 1 ]]; then
      stu_ok=1
    fi
    users_ok=0
    if [[ "${USER_COUNT}" =~ ^[0-9]+$ ]] && [[ "${USER_COUNT}" -ge 1 ]]; then
      users_ok=1
    fi
    if [[ "$stu_ok" -eq 1 && "$users_ok" -eq 1 && "${CONTAINER_FOUND}" == "YES" ]]; then
      DATABASE_SOURCE_CONFIRMED=YES
      host_user="${PG_USER:-UNKNOWN}"
      DATABASE_URL_REDACTED="postgresql://${host_user}:***@127.0.0.1:${PG_HOST_PORT_DEFAULT}/${best_db}"
    fi
    if [[ "${UNI_COUNT}" =~ ^[0-9]+$ ]] && [[ "${UNI_COUNT}" -gt 0 ]]; then
      UNIVERSITY_SOURCE=DB
    else
      UNIVERSITY_SOURCE=JSON_OR_EMPTY_DB
    fi
    if [[ "${TL_COUNT}" =~ ^[0-9]+$ ]] && [[ "${TL_COUNT}" -gt 0 ]]; then
      TIMELINE_SOURCE=DB
    else
      TIMELINE_SOURCE=CODE_TEMPLATES_OR_EMPTY_DB
    fi
    STUDENT_SOURCE=DB
  else
    echo "SCHEMA_MATCH=NO"
    warn "No DB with enough ORM tables (need >=4 hits including core SaaS tables)"
  fi
else
  warn "Skipping SQL fingerprint — container not found"
fi

# Soft compare to historical targets (do not alone decide)
echo "HISTORICAL_TARGET universities=${EXPECTED_UNI} schedules=${EXPECTED_TL} students=${EXPECTED_STU}"
echo "OBSERVED universities=${UNI_COUNT} schedules=${TL_COUNT} students=${STU_COUNT}"
if [[ "${UNI_COUNT}" == "${EXPECTED_UNI}" ]]; then echo "UNI_COUNT_MATCH=YES"; else echo "UNI_COUNT_MATCH=NO_OR_NA (may still be prod if MIXED)"; fi
if [[ "${TL_COUNT}" == "${EXPECTED_TL}" ]]; then echo "TL_COUNT_MATCH=YES"; else echo "TL_COUNT_MATCH=NO_OR_NA"; fi
if [[ "${STU_COUNT}" == "${EXPECTED_STU}" ]]; then echo "STU_COUNT_MATCH=YES"; else echo "STU_COUNT_MATCH=NO_OR_NA"; fi

# ---------- Final summary ----------
section "SUMMARY"
cat <<SUM
DISCOVERY_ONLY=${DISCOVERY_ONLY}
BRANCH=${BRANCH}
HEAD=${HEAD}
HUAQIAO_POSTGRES_FOUND=${CONTAINER_FOUND}
POSTGRES_PORT_5433=${PORT_5433}
POSTGRES_USER=${PG_USER:-UNKNOWN}
POSTGRES_DB_DEFAULT=${PG_DB:-UNKNOWN}
CANDIDATE_DBS=${CANDIDATE_DBS}
SCHEMA_MATCH=${SCHEMA_MATCH}
UNIVERSITY_COUNT=${UNI_COUNT}
TIMELINE_COUNT=${TL_COUNT}
STUDENT_COUNT=${STU_COUNT}
USER_COUNT=${USER_COUNT}
RECORD_COUNT=${RECORD_COUNT}
MEMBERSHIP_COUNT=${MEMBERSHIP_COUNT}
UNIVERSITY_SOURCE=${UNIVERSITY_SOURCE}
TIMELINE_SOURCE=${TIMELINE_SOURCE}
STUDENT_SOURCE=${STUDENT_SOURCE}
DATABASE_SOURCE_CONFIRMED=${DATABASE_SOURCE_CONFIRMED}
DATABASE_URL_REDACTED=${DATABASE_URL_REDACTED}
ENV_WRITE=NO
BACKEND_STARTED=NO
MIGRATION_RUN=NO
SEED_RUN=NO
STASH_TOUCH=NO
CNBER_TOUCH=NO
NEXT_STEP=If DATABASE_SOURCE_CONFIRMED=YES, paste this SUMMARY back; a separate restore script may then create backend/.env (not this script).
SUM

echo "============================================================"
echo "DISCOVERY_COMPLETE"
echo "============================================================"
exit 0
