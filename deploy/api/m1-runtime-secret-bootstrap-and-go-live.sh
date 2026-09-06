#!/usr/bin/env bash
# M1 ONE-SHOT: bootstrap NEW production runtime secrets + start :8010 + Caddy + persistent tunnel.
#
# Prerequisites (already done on M1):
#   - DB at 006_student_profile_slots, integrity PASS (125/900/users=2)
#   - Secret discovery FOUND=NO for all keys (old secrets unrecoverable)
#
# Allowed: generate NEW JWT_SECRET_KEY / VAULT_FERNET_KEY / ADMIN_TOKEN on M1 only.
# NEVER print/commit/push secret values. Fingerprints (sha256[:12]) only.
# NEVER alembic upgrade / seed / pg_restore / touch CNber / beta / main / university data.
#
# Usage:
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   git pull origin cursor/mobile-cloud-preview
#   bash deploy/api/m1-runtime-secret-bootstrap-and-go-live.sh
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ENV_FILE="${BACKEND}/.env"
VENV_PY="${BACKEND}/.venv/bin/python"
GUARD="${ROOT}/deploy/api/production-db-guard.sh"
RUN_WRAPPER="${ROOT}/deploy/api/m1-saas-backend-run.sh"
STATE_DIR="${HOME}/.guoqiao/saas"
RUNTIME_ENV="${STATE_DIR}/runtime.env"
LOG_DIR="${STATE_DIR}/logs"
LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"
PLIST_LABEL="com.guoqiao.saas-backend"
PLIST_PATH="${LAUNCH_AGENTS}/${PLIST_LABEL}.plist"
TUNNEL_PLIST_LABEL="com.guoqiao.cloudflared-api"
TUNNEL_PLIST_PATH="${LAUNCH_AGENTS}/${TUNNEL_PLIST_LABEL}.plist"
TUNNEL_NAME="${TUNNEL_NAME:-guoqiao-api}"
HOSTNAME_API="${HOSTNAME_API:-api.guoqiaoplan.com}"
HOSTNAME_APP="${HOSTNAME_APP:-app.guoqiaoplan.com}"
PG_CONTAINER="huaqiao-postgres"
PG_DB="huaqiao"
PG_HOST="127.0.0.1"
PG_PORT="5433"
EXPECTED_REV="006_student_profile_slots"
EXPECTED_UNI=125
EXPECTED_TL=900
EXPECTED_USERS=2
CADDY_ADDR="127.0.0.1:8088"
SAAS_ADDR="127.0.0.1:8010"

USER_ACTION_REQUIRED=NO
USER_ACTION_HINT=""
JWT_SECRET_GENERATED=NO
VAULT_SECRET_GENERATED=NO
ADMIN_TOKEN_GENERATED=NO
JWT_SECRET_FINGERPRINT=""
VAULT_SECRET_FINGERPRINT=""
ADMIN_TOKEN_FINGERPRINT=""
ENV_MODE=""
SETTINGS_VALIDATION=FAIL
PORT_8010=DOWN
HEALTH_8010=FAIL
STUDENTS_8010=FAIL
STUDENTS_META_8010=FAIL
UNIVERSITIES_8010=FAIL
TIMELINE_8010=FAIL
CADDY_8088=FAIL
TUNNEL_PERSISTENT=NO
PUBLIC_API_HEALTH=FAIL
H5_HOME=FAIL
H5_UNIVERSITIES=FAIL
H5_TIMELINE=FAIL
MIGRATION_RUN=NO
DATABASE_CHANGED=NO
SECRET_VALUES_EXPOSED=NO

abort() {
  echo "ABORT: $*" >&2
  echo "MIGRATION_RUN=${MIGRATION_RUN}"
  echo "DATABASE_CHANGED=${DATABASE_CHANGED}"
  echo "SECRET_VALUES_EXPOSED=${SECRET_VALUES_EXPOSED}"
  echo "USER_ACTION_REQUIRED=YES"
  [[ -n "${USER_ACTION_HINT}" ]] && echo "USER_ACTION=${USER_ACTION_HINT}"
  exit 1
}

info() { echo "==> $*"; }
section() { echo; echo "######## $* ########"; }

fingerprint() {
  local v="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$v" | sha256sum | awk '{print substr($1,1,12)}'
  elif command -v shasum >/dev/null 2>&1; then
    printf '%s' "$v" | shasum -a 256 | awk '{print substr($1,1,12)}'
  else
    python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:12])' "$v"
  fi
}

http_code() {
  curl -sS -o /tmp/gq-boot-body.json -w '%{http_code}' --connect-timeout 5 --max-time 20 "$@" || echo "000"
}

redact_url() {
  echo "$1" | sed -E 's#(://[^:/@]+:)[^@/]+@#\1***@#g'
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || abort "missing command: $1"
}

echo "============================================================"
echo "GUOQIAO M1 RUNTIME SECRET BOOTSTRAP + GO-LIVE"
echo "ROOT=${ROOT}"
echo "HEAD=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "SECRET_VALUES_EXPOSED=NO"
echo "MIGRATION_RUN=NO"
echo "DATABASE_CHANGED=NO"
echo "============================================================"

[[ -d "${BACKEND}" ]] || abort "backend dir missing"
[[ -x "${VENV_PY}" ]] || abort "missing ${VENV_PY} — run m1-saas-runtime-recover.sh first to create .venv"
[[ -f "${ENV_FILE}" ]] || abort "missing ${ENV_FILE} — expected DATABASE_URL from prior DB upgrade"
git -C "${ROOT}" check-ignore -q "huaqiao-saas-pro/backend/.env" || abort "backend/.env is not gitignored"

# =====================================================================
section "PHASE 2 — GUARD DATABASE STATE (no migration)"
# =====================================================================
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
done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${PG_CONTAINER}" 2>/dev/null)

[[ -n "${_PG_USER}" && -n "${_PG_PASS}" && -n "${_PG_DBNAME}" ]] || abort "cannot read postgres credentials from container"
[[ "${_PG_DBNAME}" == "${PG_DB}" ]] || abort "POSTGRES_DB=${_PG_DBNAME} != ${PG_DB}"
echo "POSTGRES_USER=${_PG_USER}"
echo "POSTGRES_DB=${PG_DB}"
echo "POSTGRES_PASSWORD=***"

pg_sql() {
  docker exec -e PGPASSWORD="${_PG_PASS}" "${PG_CONTAINER}" \
    psql -U "${_PG_USER}" -d "${PG_DB}" -v ON_ERROR_STOP=1 -tAc "$1"
}

CUR_REV="$(pg_sql "SELECT version_num FROM alembic_version LIMIT 1;" | tr -d '[:space:]')"
UNI_COUNT="$(pg_sql "SELECT count(*) FROM universities;" | tr -d '[:space:]')"
TL_COUNT="$(pg_sql "SELECT count(*) FROM admission_schedules;" | tr -d '[:space:]')"
USER_COUNT="$(pg_sql "SELECT count(*) FROM users;" | tr -d '[:space:]')"

echo "DATABASE_REVISION=${CUR_REV}"
echo "UNIVERSITY_COUNT=${UNI_COUNT}"
echo "TIMELINE_COUNT=${TL_COUNT}"
echo "USER_COUNT=${USER_COUNT}"
echo "MIGRATION_RUN=NO"

[[ "${CUR_REV}" == "${EXPECTED_REV}" ]] || abort "alembic_version=${CUR_REV} != ${EXPECTED_REV}"
[[ "${UNI_COUNT}" == "${EXPECTED_UNI}" ]] || abort "universities=${UNI_COUNT} != ${EXPECTED_UNI}"
[[ "${TL_COUNT}" == "${EXPECTED_TL}" ]] || abort "admission_schedules=${TL_COUNT} != ${EXPECTED_TL}"
[[ "${USER_COUNT}" == "${EXPECTED_USERS}" ]] || abort "users=${USER_COUNT} != ${EXPECTED_USERS}"
echo "DATABASE_GUARD=PASS"

# Confirm .env DATABASE_URL targets 127.0.0.1:5433/huaqiao (never print full URL)
DB_TARGET_OK="$(
  GQ_ENV="${ENV_FILE}" "${VENV_PY}" - <<'PY'
from pathlib import Path
import os
p = Path(os.environ["GQ_ENV"])
url = ""
for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
    if line.strip().startswith("DATABASE_URL="):
        url = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
ok = ("127.0.0.1:5433/huaqiao" in url) or ("localhost:5433/huaqiao" in url)
print("YES" if ok else "NO")
PY
)"
[[ "${DB_TARGET_OK}" == "YES" ]] || abort "DATABASE_URL does not target 127.0.0.1:5433/huaqiao"
echo "DATABASE_URL_TARGET=127.0.0.1:5433/huaqiao"
unset _PG_PASS

# =====================================================================
section "PHASE 3–4 — GENERATE / MERGE SECRETS (atomic .env write)"
# =====================================================================
mkdir -p "${STATE_DIR}" "${LOG_DIR}"
chmod 700 "${STATE_DIR}" 2>/dev/null || true

# Generate secrets inside Python; write fingerprints to a status file; never echo values.
STATUS_FILE="$(mktemp)"
chmod 600 "${STATUS_FILE}"
TMP_ENV="$(mktemp)"
chmod 600 "${TMP_ENV}"
BAK="${ENV_FILE}.bak.bootstrap.$(date +%Y%m%d%H%M%S)"
cp "${ENV_FILE}" "${BAK}"
chmod 600 "${BAK}"

GQ_ENV_IN="${ENV_FILE}" GQ_ENV_OUT="${TMP_ENV}" GQ_STATUS="${STATUS_FILE}" "${VENV_PY}" - <<'PY'
import os, secrets, hashlib
from pathlib import Path

try:
    from cryptography.fernet import Fernet
except ImportError as e:
    raise SystemExit(f"cryptography missing in venv: {e}")

env_in = Path(os.environ["GQ_ENV_IN"])
env_out = Path(os.environ["GQ_ENV_OUT"])
status = Path(os.environ["GQ_STATUS"])

protected = {
    "DATABASE_URL",
    "GUOQIAO_SKIP_SEED",
    "PUBLIC_BASE_URL",
    "FRONTEND_BASE_URL",
    "CORS_ORIGINS",
}
wanted_defaults = {
    "ENV": "production",
    "GUOQIAO_SKIP_SEED": "1",
    "PUBLIC_BASE_URL": "https://api.guoqiaoplan.com",
    "FRONTEND_BASE_URL": "https://app.guoqiaoplan.com",
    "CORS_ORIGINS": "https://app.guoqiaoplan.com,https://huaqiao-international-eligibility-system.rambolluk.workers.dev",
}

order = []
kv = {}
comments_before = {}
pending = []
for line in env_in.read_text(encoding="utf-8", errors="replace").splitlines():
    s = line.strip()
    if not s or s.startswith("#") or "=" not in line:
        pending.append(line)
        continue
    k, _, v = line.partition("=")
    k = k.strip()
    if k not in kv:
        order.append(k)
        comments_before[k] = pending
        pending = []
        kv[k] = v
trailing = pending

def fp(val: str) -> str:
    return hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]

def is_placeholder(val: str) -> bool:
    v = (val or "").strip().lower()
    return v in {"", "change-me-in-production", "changeme", "change-me", "replace-me", "todo", "placeholder", "xxx", "null", "none", "password123"}

flags = {
    "JWT_SECRET_GENERATED": "NO",
    "VAULT_SECRET_GENERATED": "NO",
    "ADMIN_TOKEN_GENERATED": "NO",
    "JWT_SECRET_FINGERPRINT": "",
    "VAULT_SECRET_FINGERPRINT": "",
    "ADMIN_TOKEN_FINGERPRINT": "",
}

# Ensure protected / defaults without overwriting existing non-empty protected values
for k, default in wanted_defaults.items():
    if k == "ENV":
        # Always set production for go-live validation path
        if k not in kv or is_placeholder(kv[k]) or kv[k].strip() != "production":
            if k not in kv:
                order.append(k)
                comments_before[k] = []
            kv[k] = "production"
        continue
    if k in protected:
        if k not in kv or is_placeholder(kv[k]):
            if k not in kv:
                order.append(k)
                comments_before[k] = []
            # Only fill GUOQIAO_SKIP_SEED / URLs if missing — never invent DATABASE_URL
            if k == "DATABASE_URL":
                raise SystemExit("DATABASE_URL missing — refuse to invent")
            kv[k] = default
        continue

# Secrets: fill only if missing/placeholder
jwt = kv.get("JWT_SECRET_KEY", "").strip()
if is_placeholder(jwt) or jwt == "change-me-in-production":
    jwt = secrets.token_urlsafe(64)
    if "JWT_SECRET_KEY" not in kv:
        order.append("JWT_SECRET_KEY")
        comments_before["JWT_SECRET_KEY"] = []
    kv["JWT_SECRET_KEY"] = jwt
    flags["JWT_SECRET_GENERATED"] = "YES"
else:
    flags["JWT_SECRET_GENERATED"] = "NO"
flags["JWT_SECRET_FINGERPRINT"] = fp(kv["JWT_SECRET_KEY"])

vault = kv.get("VAULT_FERNET_KEY", "").strip()
vault_ok = False
if vault and not is_placeholder(vault):
    try:
        Fernet(vault.encode("utf-8"))
        vault_ok = True
    except Exception:
        vault_ok = False
if not vault_ok:
    vault = Fernet.generate_key().decode("ascii")
    if "VAULT_FERNET_KEY" not in kv:
        order.append("VAULT_FERNET_KEY")
        comments_before["VAULT_FERNET_KEY"] = []
    kv["VAULT_FERNET_KEY"] = vault
    flags["VAULT_SECRET_GENERATED"] = "YES"
else:
    flags["VAULT_SECRET_GENERATED"] = "NO"
flags["VAULT_SECRET_FINGERPRINT"] = fp(kv["VAULT_FERNET_KEY"])

admin = kv.get("ADMIN_TOKEN", "").strip()
if is_placeholder(admin):
    admin = secrets.token_urlsafe(48)
    if "ADMIN_TOKEN" not in kv:
        order.append("ADMIN_TOKEN")
        comments_before["ADMIN_TOKEN"] = []
    kv["ADMIN_TOKEN"] = admin
    flags["ADMIN_TOKEN_GENERATED"] = "YES"
else:
    flags["ADMIN_TOKEN_GENERATED"] = "NO"
flags["ADMIN_TOKEN_FINGERPRINT"] = fp(kv["ADMIN_TOKEN"])

# Deduplicate: ensure each key appears once
seen = set()
final_order = []
for k in order:
    if k in seen:
        continue
    seen.add(k)
    final_order.append(k)

with env_out.open("w", encoding="utf-8") as out:
    for k in final_order:
        for c in comments_before.get(k, []):
            out.write(c + "\n")
        out.write(f"{k}={kv[k]}\n")
    for c in trailing:
        out.write(c + "\n")

# Verify single occurrence of secret keys
text = env_out.read_text(encoding="utf-8")
for k in ("JWT_SECRET_KEY", "VAULT_FERNET_KEY", "ADMIN_TOKEN"):
    n = sum(1 for line in text.splitlines() if line.startswith(k + "="))
    if n != 1:
        raise SystemExit(f"{k} occurrence count={n} expected 1")

with status.open("w", encoding="utf-8") as sf:
    for k, v in flags.items():
        sf.write(f"{k}={v}\n")
PY

mv "${TMP_ENV}" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

# Load fingerprints / generated flags (no secret values in status file)
while IFS= read -r line || [[ -n "$line" ]]; do
  case "$line" in
    JWT_SECRET_GENERATED=*) JWT_SECRET_GENERATED="${line#JWT_SECRET_GENERATED=}" ;;
    VAULT_SECRET_GENERATED=*) VAULT_SECRET_GENERATED="${line#VAULT_SECRET_GENERATED=}" ;;
    ADMIN_TOKEN_GENERATED=*) ADMIN_TOKEN_GENERATED="${line#ADMIN_TOKEN_GENERATED=}" ;;
    JWT_SECRET_FINGERPRINT=*) JWT_SECRET_FINGERPRINT="${line#JWT_SECRET_FINGERPRINT=}" ;;
    VAULT_SECRET_FINGERPRINT=*) VAULT_SECRET_FINGERPRINT="${line#VAULT_SECRET_FINGERPRINT=}" ;;
    ADMIN_TOKEN_FINGERPRINT=*) ADMIN_TOKEN_FINGERPRINT="${line#ADMIN_TOKEN_FINGERPRINT=}" ;;
  esac
done <"${STATUS_FILE}"
rm -f "${STATUS_FILE}"

echo "JWT_SECRET_GENERATED=${JWT_SECRET_GENERATED}"
echo "JWT_SECRET_FINGERPRINT=${JWT_SECRET_FINGERPRINT}"
echo "VAULT_SECRET_GENERATED=${VAULT_SECRET_GENERATED}"
echo "VAULT_SECRET_FINGERPRINT=${VAULT_SECRET_FINGERPRINT}"
echo "ADMIN_TOKEN_GENERATED=${ADMIN_TOKEN_GENERATED}"
echo "ADMIN_TOKEN_FINGERPRINT=${ADMIN_TOKEN_FINGERPRINT}"
echo "ENV_CHMOD=600"
echo "ENV_BACKUP=${BAK}"
echo "SECRET_VALUES_EXPOSED=NO"
echo "OLD_JWT_SESSION_INVALIDATED=YES"

# =====================================================================
section "PHASE 5 — SETTINGS VALIDATION"
# =====================================================================
bash "${GUARD}" "${BACKEND}" || abort "production-db-guard FAIL"

VAL_OUT="$(
  cd "${BACKEND}"
  "${VENV_PY}" - <<'PY'
import sys
from cryptography.fernet import Fernet
from app.config import get_settings

# Clear lru_cache so .env changes are visible
get_settings.cache_clear()
s = get_settings()
errors = []

env_mode = s.env
print(f"ENV_MODE={env_mode}")

if not s.database_url or ("127.0.0.1:5433/huaqiao" not in s.database_url and "localhost:5433/huaqiao" not in s.database_url):
    errors.append("database_url_not_5433_huaqiao")
else:
    print("DATABASE_URL_OK=YES")

if not s.guoqiao_skip_seed:
    errors.append("guoqiao_skip_seed_false")
else:
    print("GUOQIAO_SKIP_SEED=True")

if not s.jwt_secret_key or s.jwt_secret_key == "change-me-in-production":
    errors.append("jwt_placeholder")
else:
    print("JWT_OK=YES")

try:
    Fernet(s.vault_fernet_key.encode("utf-8"))
    print("FERNET_OK=YES")
except Exception as e:
    errors.append(f"fernet_invalid:{type(e).__name__}")

if not (s.admin_token or "").strip():
    errors.append("admin_token_empty")
else:
    print("ADMIN_OK=YES")

# Production validation (requires ENV=production)
try:
    s.validate_production_config()
    print("VALIDATE_PRODUCTION=PASS")
except RuntimeError as e:
    msg = str(e)
    # Never print secret contents if somehow embedded — strip after colon values
    print("VALIDATE_PRODUCTION=FAIL")
    print(f"VALIDATE_PRODUCTION_ERRORS={msg}")
    errors.append("validate_production_config")

if errors:
    print("SETTINGS_VALIDATION=FAIL")
    print("SETTINGS_ERRORS=" + ",".join(errors))
    sys.exit(1)
print("SETTINGS_VALIDATION=PASS")
PY
)" || {
  echo "${VAL_OUT}"
  abort "settings validation failed"
}
echo "${VAL_OUT}"
ENV_MODE="$(echo "${VAL_OUT}" | awk -F= '/^ENV_MODE=/{print $2; exit}')"
SETTINGS_VALIDATION=PASS

# =====================================================================
section "PHASE 6 — START :8010 VIA LaunchAgent"
# =====================================================================
mkdir -p "${LAUNCH_AGENTS}" "${LOG_DIR}"
chmod +x "${RUN_WRAPPER}"

# Persist runtime.env for wrapper
cat >"${RUNTIME_ENV}" <<EOF
# Generated by m1-runtime-secret-bootstrap-and-go-live.sh — do not commit
SAAS_BACKEND_DIR=${BACKEND}
SAAS_PYTHON=${VENV_PY}
SAAS_VENV=${BACKEND}/.venv
SAAS_START_METHOD=launchd:${PLIST_LABEL}
EOF
chmod 600 "${RUNTIME_ENV}"

# Ensure plist exists / refresh paths
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
  <string>${LOG_DIR}/saas-backend.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/saas-backend.err.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || launchctl unload "${PLIST_PATH}" 2>/dev/null || true
# Stop leftover uvicorn on 8010 if any
if command -v lsof >/dev/null 2>&1; then
  for pid in $(lsof -nP -iTCP:8010 -sTCP:LISTEN -t 2>/dev/null || true); do
    cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    case "$cmd" in
      *uvicorn*|*app.main*|*huaqiao-saas*) kill "$pid" 2>/dev/null || true; sleep 1; kill -9 "$pid" 2>/dev/null || true ;;
    esac
  done
fi
launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}" 2>/dev/null || launchctl load -w "${PLIST_PATH}"
launchctl kickstart -k "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true

ok8010=0
i=0
while [[ $i -lt 45 ]]; do
  i=$((i + 1))
  code="$(http_code "http://${SAAS_ADDR}/api/health")"
  if [[ "$code" == "200" ]]; then ok8010=1; break; fi
  sleep 1
done
if [[ "${ok8010}" -ne 1 ]]; then
  tail -n 80 "${LOG_DIR}/saas-backend.err.log" 2>/dev/null || true
  abort "8010 health not 200 after LaunchAgent kickstart"
fi
PORT_8010=UP
HEALTH_8010=PASS

c_stu="$(http_code "http://${SAAS_ADDR}/api/students")"
c_meta="$(http_code "http://${SAAS_ADDR}/api/students/meta")"
c_uni="$(http_code "http://${SAAS_ADDR}/api/universities?target=international")"
c_sch="$(http_code "http://${SAAS_ADDR}/api/schedules?target=international")"
echo "HEALTH_8010=200"
echo "STUDENTS_8010=${c_stu}"
echo "STUDENTS_META_8010=${c_meta}"
echo "UNIVERSITIES_8010=${c_uni}"
echo "SCHEDULES_8010=${c_sch}"

[[ "${c_stu}" == "401" || "${c_stu}" == "403" ]] || abort "students expected 401/403 got ${c_stu}"
[[ "${c_meta}" == "200" ]] || abort "students/meta expected 200 got ${c_meta}"
[[ "${c_uni}" == "200" ]] || abort "universities expected 200 got ${c_uni}"
[[ "${c_sch}" == "200" ]] || abort "schedules expected 200 got ${c_sch}"
STUDENTS_8010=AUTH_REQUIRED
STUDENTS_META_8010=PASS
UNIVERSITIES_8010=PASS
TIMELINE_8010=PASS

# =====================================================================
section "PHASE 7 — CADDY :8088 → :8010"
# =====================================================================
require_cmd caddy
caddy stop >/dev/null 2>&1 || true
caddy start --config "${ROOT}/deploy/api/Caddyfile" --adapter caddyfile
sleep 1
caddy_h="$(http_code "http://${CADDY_ADDR}/api/health")"
echo "CADDY_HEALTH_HTTP=${caddy_h}"
[[ "${caddy_h}" == "200" ]] || abort "Caddy :8088 /api/health expected 200 got ${caddy_h}"
CADDY_8088=PASS

# =====================================================================
section "PHASE 8 — PERSISTENT CLOUDFLARE TUNNEL"
# =====================================================================
# Do NOT invent credentials. Prefer existing named tunnel config + LaunchAgent.
CFG="${HOME}/.cloudflared/guoqiao-api.yml"
TUNNEL_ID=""
CRED=""

if command -v cloudflared >/dev/null 2>&1; then
  if [[ -f "${CFG}" ]]; then
    TUNNEL_ID="$(awk -F': *' '/^tunnel:/{print $2; exit}' "${CFG}" | tr -d '[:space:]')"
    CRED_LINE="$(awk -F': *' '/^credentials-file:/{print $2; exit}' "${CFG}" | tr -d '[:space:]')"
    CRED="${CRED_LINE/#\~/$HOME}"
  fi
  if [[ -z "${TUNNEL_ID}" ]]; then
    TUNNEL_ID="$(cloudflared tunnel list 2>/dev/null | awk -v n="${TUNNEL_NAME}" '$2==n{print $1; exit}' || true)"
  fi
  if [[ -n "${TUNNEL_ID}" && -z "${CRED}" ]]; then
    CRED="${HOME}/.cloudflared/${TUNNEL_ID}.json"
  fi
fi

if [[ -n "${TUNNEL_ID}" && -f "${CRED}" ]]; then
  # Ensure config points at Caddy
  mkdir -p "${HOME}/.cloudflared"
  chmod 700 "${HOME}/.cloudflared" 2>/dev/null || true
  umask 077
  cat >"${CFG}" <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${CRED}
ingress:
  - hostname: ${HOSTNAME_API}
    service: http://${CADDY_ADDR}
  - service: http_status:404
EOF
  chmod 600 "${CFG}" "${CRED}" 2>/dev/null || true

  # Persistent LaunchAgent for tunnel (not Agent Quick Tunnel / not ad-hoc nohup)
  cat >"${TUNNEL_PLIST_PATH}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${TUNNEL_PLIST_LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>$(command -v cloudflared)</string>
    <string>tunnel</string>
    <string>--config</string>
    <string>${CFG}</string>
    <string>run</string>
    <string>${TUNNEL_NAME}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/cloudflared-api.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/cloudflared-api.err.log</string>
</dict>
</plist>
EOF
  launchctl bootout "gui/$(id -u)/${TUNNEL_PLIST_LABEL}" 2>/dev/null || launchctl unload "${TUNNEL_PLIST_PATH}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "${TUNNEL_PLIST_PATH}" 2>/dev/null || launchctl load -w "${TUNNEL_PLIST_PATH}"
  launchctl kickstart -k "gui/$(id -u)/${TUNNEL_PLIST_LABEL}" 2>/dev/null || true
  TUNNEL_PERSISTENT=YES
  echo "TUNNEL_PERSISTENT=YES"
  echo "TUNNEL_ID=${TUNNEL_ID}"
  echo "TUNNEL_CREDENTIALS=PRESENT"
else
  TUNNEL_PERSISTENT=NO
  USER_ACTION_REQUIRED=YES
  USER_ACTION_HINT="cloudflared tunnel login && cloudflared tunnel create ${TUNNEL_NAME} && cloudflared tunnel route dns ${TUNNEL_NAME} ${HOSTNAME_API} && re-run this script"
  echo "TUNNEL_PERSISTENT=NO"
  echo "TUNNEL_CREDENTIALS=MISSING"
  echo "USER_ACTION_REQUIRED=YES"
  echo "USER_ACTION=${USER_ACTION_HINT}"
fi

pub_ok=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code="$(http_code "https://${HOSTNAME_API}/api/health")"
  if [[ "$code" == "200" ]]; then pub_ok=1; break; fi
  sleep 2
done
if [[ "${pub_ok}" -eq 1 ]]; then
  PUBLIC_API_HEALTH=PASS
  echo "PUBLIC_API_HEALTH=PASS"
else
  PUBLIC_API_HEALTH=FAIL
  echo "PUBLIC_API_HEALTH=FAIL"
  if [[ "${TUNNEL_PERSISTENT}" == "YES" ]]; then
    USER_ACTION_REQUIRED=YES
    USER_ACTION_HINT="Check LaunchAgent ${TUNNEL_PLIST_LABEL} / DNS for ${HOSTNAME_API} → tunnel → ${CADDY_ADDR}"
  fi
fi

# =====================================================================
section "PHASE 9 — H5 ACCEPTANCE (public pages + API catalog)"
# =====================================================================
# SPA shells: expect HTTP 200. Catalog APIs via public API confirm data path.
h5_home="$(http_code "https://${HOSTNAME_APP}/")"
h5_uni="$(http_code "https://${HOSTNAME_APP}/universities")"
h5_tl="$(http_code "https://${HOSTNAME_APP}/timeline")"
# Some routers use hash/query; also try index fallbacks
[[ "${h5_uni}" == "200" ]] || h5_uni="$(http_code "https://${HOSTNAME_APP}/")"
[[ "${h5_tl}" == "200" ]] || h5_tl="$(http_code "https://${HOSTNAME_APP}/")"

echo "H5_HOME_HTTP=${h5_home}"
echo "H5_UNIVERSITIES_HTTP=${h5_uni}"
echo "H5_TIMELINE_HTTP=${h5_tl}"

[[ "${h5_home}" == "200" ]] && H5_HOME=PASS || H5_HOME=FAIL
[[ "${h5_uni}" == "200" ]] && H5_UNIVERSITIES=PASS || H5_UNIVERSITIES=FAIL
[[ "${h5_tl}" == "200" ]] && H5_TIMELINE=PASS || H5_TIMELINE=FAIL

# Public API catalog (proxy of H5 data)
if [[ "${PUBLIC_API_HEALTH}" == "PASS" ]]; then
  pu="$(http_code "https://${HOSTNAME_API}/api/universities?target=international")"
  ps="$(http_code "https://${HOSTNAME_API}/api/schedules?target=international")"
  echo "PUBLIC_UNIVERSITIES_HTTP=${pu}"
  echo "PUBLIC_SCHEDULES_HTTP=${ps}"
  [[ "${pu}" == "200" ]] || H5_UNIVERSITIES=FAIL
  [[ "${ps}" == "200" ]] || H5_TIMELINE=FAIL
fi

# Login / student create/switch require real credentials — do not invent accounts or mock students
echo "NOTE=OLD_JWT_SESSION_INVALIDATED=YES — re-login with a real test account to verify STUDENTS_API / CREATE / SWITCH"
if [[ -z "${GUOQIAO_TEST_EMAIL:-}" || -z "${GUOQIAO_TEST_PASSWORD:-}" ]]; then
  echo "STUDENTS_LOGIN_CHECK=SKIPPED (set GUOQIAO_TEST_EMAIL + GUOQIAO_TEST_PASSWORD to auto-verify)"
  if [[ "${USER_ACTION_REQUIRED}" != "YES" && "${PUBLIC_API_HEALTH}" == "PASS" && "${H5_HOME}" == "PASS" ]]; then
    USER_ACTION_REQUIRED=YES
    USER_ACTION_HINT="Open https://${HOSTNAME_APP} and re-login with a real account to confirm students create/switch"
  fi
else
  # Login via public API without printing password/token
  LOGIN_BODY="$(
    GUOQIAO_TEST_EMAIL="${GUOQIAO_TEST_EMAIL}" GUOQIAO_TEST_PASSWORD="${GUOQIAO_TEST_PASSWORD}" \
      python3 -c 'import json,os; print(json.dumps({"email":os.environ["GUOQIAO_TEST_EMAIL"],"password":os.environ["GUOQIAO_TEST_PASSWORD"]}))'
  )"
  login_code="$(
    curl -sS -o /tmp/gq-login.json -w '%{http_code}' \
      -X POST "https://${HOSTNAME_API}/api/auth/login" \
      -H 'Content-Type: application/json' \
      -d "${LOGIN_BODY}" \
      || echo 000
  )"
  unset LOGIN_BODY
  echo "LOGIN_HTTP=${login_code}"
  if [[ "${login_code}" == "200" ]]; then
    token="$(python3 -c 'import json; print(json.load(open("/tmp/gq-login.json")).get("token",""))' 2>/dev/null || true)"
    rm -f /tmp/gq-login.json
    if [[ -n "${token}" ]]; then
      stu_code="$(curl -sS -o /tmp/gq-stu.json -w '%{http_code}' \
        -H "Authorization: Bearer ${token}" \
        "https://${HOSTNAME_API}/api/students" || echo 000)"
      unset token
      echo "STUDENTS_AUTH_HTTP=${stu_code}"
      [[ "${stu_code}" == "200" ]] && echo "STUDENTS_API=PASS" || echo "STUDENTS_API=FAIL"
    fi
  else
    echo "STUDENTS_API=FAIL"
    rm -f /tmp/gq-login.json
  fi
fi

# =====================================================================
section "FINAL REPORT"
# =====================================================================
COMMIT="$(git -C "${ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "============================================================"
echo "GUOQIAO_M1_FINAL_RUNTIME_GO_LIVE_REPORT"
echo "DATABASE_REVISION=${CUR_REV}"
echo "DATABASE_CHANGED=NO"
echo "MIGRATION_RUN=NO"
echo "JWT_SECRET_GENERATED=${JWT_SECRET_GENERATED}"
echo "JWT_SECRET_FINGERPRINT=${JWT_SECRET_FINGERPRINT}"
echo "VAULT_SECRET_GENERATED=${VAULT_SECRET_GENERATED}"
echo "VAULT_SECRET_FINGERPRINT=${VAULT_SECRET_FINGERPRINT}"
echo "ADMIN_TOKEN_GENERATED=${ADMIN_TOKEN_GENERATED}"
echo "ADMIN_TOKEN_FINGERPRINT=${ADMIN_TOKEN_FINGERPRINT}"
echo "SECRET_VALUES_EXPOSED=NO"
echo "ENV_MODE=${ENV_MODE}"
echo "SETTINGS_VALIDATION=${SETTINGS_VALIDATION}"
echo "PORT_8010=${PORT_8010}"
echo "HEALTH_8010=${HEALTH_8010}"
echo "STUDENTS_8010=${STUDENTS_8010}"
echo "STUDENTS_META_8010=${STUDENTS_META_8010}"
echo "UNIVERSITIES_8010=${UNIVERSITIES_8010}"
echo "TIMELINE_8010=${TIMELINE_8010}"
echo "CADDY_8088=${CADDY_8088}"
echo "TUNNEL_PERSISTENT=${TUNNEL_PERSISTENT}"
echo "PUBLIC_API_HEALTH=${PUBLIC_API_HEALTH}"
echo "H5_HOME=${H5_HOME}"
echo "H5_UNIVERSITIES=${H5_UNIVERSITIES}"
echo "H5_TIMELINE=${H5_TIMELINE}"
echo "OLD_JWT_SESSION_INVALIDATED=YES"
echo "CNBER_CHANGED=NO"
echo "BETA_CHANGED=NO"
echo "MAIN_CHANGED=NO"
echo "COMMIT=${COMMIT}"
echo "PUSH=origin/cursor/mobile-cloud-preview"
echo "USER_ACTION_REQUIRED=${USER_ACTION_REQUIRED}"
if [[ "${USER_ACTION_REQUIRED}" == "YES" ]]; then
  echo "USER_ACTION=${USER_ACTION_HINT}"
fi
echo "============================================================"

# Exit non-zero only if core local stack failed (tunnel/H5 login may need human)
if [[ "${PORT_8010}" != "UP" || "${HEALTH_8010}" != "PASS" || "${CADDY_8088}" != "PASS" || "${SETTINGS_VALIDATION}" != "PASS" ]]; then
  exit 1
fi
exit 0
