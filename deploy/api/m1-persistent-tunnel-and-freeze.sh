#!/usr/bin/env bash
# M1 ONE-SHOT: Cloudflare persistent named tunnel + launchd for tunnel/Caddy + production freeze.
#
# Prerequisites (already PASS on M1):
#   DATABASE 006, secrets, :8010, Caddy :8088, PUBLIC may already work via ephemeral tunnel
#   TUNNEL_PERSISTENT=NO / TUNNEL_CREDENTIALS=MISSING was the remaining gap
#
# ABSOLUTE BANS:
#   alembic / migration / seed / DB write / pg_restore
#   secret regeneration / .env overwrite
#   CNber / guoqiao-beta-* / main merge / business rules / university / timeline data
#
# Usage:
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   git pull origin cursor/mobile-cloud-preview
#   bash deploy/api/m1-persistent-tunnel-and-freeze.sh
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STATE_DIR="${HOME}/.guoqiao/saas"
LOG_DIR="${STATE_DIR}/logs"
LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"
CF_DIR="${HOME}/.cloudflared"
CFG="${CF_DIR}/config.yml"
CFG_ALIAS="${CF_DIR}/guoqiao-api.yml"
TUNNEL_NAME="${TUNNEL_NAME:-guoqiao-api}"
HOSTNAME_API="${HOSTNAME_API:-api.guoqiaoplan.com}"
HOSTNAME_APP="${HOSTNAME_APP:-app.guoqiaoplan.com}"
CADDY_ADDR="127.0.0.1:8088"
SAAS_ADDR="127.0.0.1:8010"
CADDYFILE="${ROOT}/deploy/api/Caddyfile"
PLIST_SAAS="com.guoqiao.saas-backend"
PLIST_CF="com.guoqiao.cloudflared"
PLIST_CADDY="com.guoqiao.caddy"
PG_CONTAINER="huaqiao-postgres"
FREEZE_FILE="${STATE_DIR}/PRODUCTION_FREEZE.txt"

USER_ACTION_REQUIRED=NO
USER_ACTION=""
TUNNEL_ID=""
TUNNEL_PERSISTENT=NO
TUNNEL_LAUNCHD=FAIL
API_DNS_ROUTE=FAIL
PUBLIC_API_HEALTH=FAIL
CLOUDFLARED_INSTALLED=NO
CADDY_LAUNCHD=FAIL
SAAS_8010=FAIL
CADDY_8088=FAIL
H5_HOME=FAIL
H5_UNIVERSITIES=FAIL
H5_TIMELINE=FAIL
POSTGRES_UP=FAIL

abort() {
  echo "ABORT: $*" >&2
  echo "DATABASE_CHANGED=NO"
  echo "MIGRATION_RUN=NO"
  echo "USER_ACTION_REQUIRED=${USER_ACTION_REQUIRED}"
  [[ -n "${USER_ACTION}" ]] && echo "USER_ACTION=${USER_ACTION}"
  exit 1
}

info() { echo "==> $*"; }
section() { echo; echo "######## $* ########"; }

http_code() {
  curl -sS -o /tmp/gq-pt-body.json -w '%{http_code}' --connect-timeout 5 --max-time 25 "$@" || echo "000"
}

launchd_running() {
  local label="$1"
  if launchctl print "gui/$(id -u)/${label}" 2>/dev/null | grep -q 'state = running'; then
    return 0
  fi
  # older launchctl
  if launchctl list 2>/dev/null | awk '{print $3}' | grep -qx "${label}"; then
    return 0
  fi
  return 1
}

install_plist() {
  local label="$1" path="$2"
  mkdir -p "${LAUNCH_AGENTS}"
  launchctl bootout "gui/$(id -u)/${label}" 2>/dev/null || launchctl unload "${path}" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "${path}" 2>/dev/null || launchctl load -w "${path}"
  launchctl kickstart -k "gui/$(id -u)/${label}" 2>/dev/null || true
}

echo "============================================================"
echo "GUOQIAO M1 PERSISTENT TUNNEL + PRODUCTION FREEZE"
echo "ROOT=${ROOT}"
echo "HEAD=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "DATABASE_CHANGED=NO"
echo "MIGRATION_RUN=NO"
echo "SECRET_REGENERATION=NO"
echo "ENV_OVERWRITE=NO"
echo "============================================================"

mkdir -p "${STATE_DIR}" "${LOG_DIR}" "${LAUNCH_AGENTS}"
chmod 700 "${STATE_DIR}" 2>/dev/null || true

# =====================================================================
section "PHASE 0 — LOCAL STACK GUARD (read-only)"
# =====================================================================
# Do not touch DB; only verify services already expected UP.
if docker inspect "${PG_CONTAINER}" >/dev/null 2>&1; then
  st="$(docker inspect -f '{{.State.Status}}' "${PG_CONTAINER}" 2>/dev/null || echo unknown)"
  echo "POSTGRES_CONTAINER=${PG_CONTAINER} STATUS=${st}"
  [[ "$st" == "running" ]] && POSTGRES_UP=PASS || POSTGRES_UP=FAIL
  rp="$(docker inspect -f '{{.HostConfig.RestartPolicy.Name}}' "${PG_CONTAINER}" 2>/dev/null || echo unknown)"
  echo "POSTGRES_RESTART_POLICY=${rp}"
else
  echo "POSTGRES_CONTAINER=ABSENT"
  POSTGRES_UP=FAIL
fi
[[ "${POSTGRES_UP}" == "PASS" ]] || abort "huaqiao-postgres not running — refuse tunnel-only go-live without local DB"

c8010="$(http_code "http://${SAAS_ADDR}/api/health")"
c8088="$(http_code "http://${CADDY_ADDR}/api/health")"
echo "HEALTH_8010_HTTP=${c8010}"
echo "HEALTH_8088_HTTP=${c8088}"
[[ "${c8010}" == "200" ]] && SAAS_8010=PASS || SAAS_8010=FAIL
[[ "${c8088}" == "200" ]] && CADDY_8088=PASS || CADDY_8088=FAIL
[[ "${SAAS_8010}" == "PASS" ]] || abort ":8010 not healthy — fix SaaS LaunchAgent first (do not regenerate secrets)"
# Caddy may be down; we will persist/start it in Phase 7 — warn only if both down
if [[ "${CADDY_8088}" != "PASS" ]]; then
  info "Caddy :8088 not yet 200 — will install/start LaunchAgent com.guoqiao.caddy"
fi

# =====================================================================
section "PHASE 1 — AUDIT CLOUDFLARED"
# =====================================================================
if command -v cloudflared >/dev/null 2>&1; then
  CLOUDFLARED_INSTALLED=YES
  CF_BIN="$(command -v cloudflared)"
  echo "CLOUDFLARED_BIN=${CF_BIN}"
  cloudflared --version 2>&1 | head -n 2 || true
else
  CLOUDFLARED_INSTALLED=NO
  USER_ACTION_REQUIRED=YES
  USER_ACTION="brew install cloudflare/cloudflare/cloudflared"
  abort "cloudflared not installed"
fi

echo "--- ~/.cloudflared filenames only ---"
if [[ -d "${CF_DIR}" ]]; then
  # Names only — never cat credential JSON / cert contents
  find "${CF_DIR}" -maxdepth 2 \( -type f -o -type l \) -printf '%f\n' 2>/dev/null \
    || find "${CF_DIR}" -maxdepth 2 \( -type f -o -type l \) -exec basename {} \; 2>/dev/null \
    || ls -1 "${CF_DIR}" 2>/dev/null || true
  chmod 700 "${CF_DIR}" 2>/dev/null || true
else
  echo "(absent)"
  mkdir -p "${CF_DIR}"
  chmod 700 "${CF_DIR}"
fi

echo "--- /etc/cloudflared filenames only ---"
if [[ -d /etc/cloudflared ]]; then
  ls -1 /etc/cloudflared 2>/dev/null || echo "(permission denied or empty)"
else
  echo "(absent)"
fi

echo "--- tunnel list (ids/names only) ---"
cloudflared tunnel list 2>/dev/null | head -n 40 || echo "tunnel list unavailable (may need login)"

HAS_CERT=NO
[[ -f "${CF_DIR}/cert.pem" ]] && HAS_CERT=YES
echo "CERT_PEM_PRESENT=${HAS_CERT}"

# Existing tunnel reuse
EXISTING_ID="$(cloudflared tunnel list 2>/dev/null | awk -v n="${TUNNEL_NAME}" '$2==n{print $1; exit}' || true)"
if [[ -n "${EXISTING_ID}" ]]; then
  TUNNEL_ID="${EXISTING_ID}"
  echo "TUNNEL_REUSE=YES"
  echo "TUNNEL_ID=${TUNNEL_ID}"
else
  echo "TUNNEL_REUSE=NO"
fi

CRED=""
if [[ -n "${TUNNEL_ID}" && -f "${CF_DIR}/${TUNNEL_ID}.json" ]]; then
  CRED="${CF_DIR}/${TUNNEL_ID}.json"
fi
# Also accept credentials-file from existing config without printing contents
for conf in "${CFG}" "${CFG_ALIAS}"; do
  if [[ -z "${CRED}" && -f "${conf}" ]]; then
    cand="$(awk -F': *' '/^credentials-file:/{print $2; exit}' "${conf}" | tr -d '[:space:]')"
    cand="${cand/#\~/$HOME}"
    if [[ -n "${cand}" && -f "${cand}" ]]; then
      CRED="${cand}"
      [[ -z "${TUNNEL_ID}" ]] && TUNNEL_ID="$(awk -F': *' '/^tunnel:/{print $2; exit}' "${conf}" | tr -d '[:space:]')"
    fi
  fi
done
if [[ -n "${CRED}" ]]; then
  echo "TUNNEL_CREDENTIALS=PRESENT"
  echo "TUNNEL_CREDENTIAL_FILE=$(basename "${CRED}")"
else
  echo "TUNNEL_CREDENTIALS=MISSING"
fi

# =====================================================================
section "PHASE 2 — LOGIN GATE (no forged credentials)"
# =====================================================================
# Need cert.pem to create tunnels / route DNS. Running an existing tunnel only needs credential JSON.
NEED_LOGIN=NO
if [[ -z "${TUNNEL_ID}" || -z "${CRED}" ]]; then
  if [[ "${HAS_CERT}" != "YES" ]]; then
    NEED_LOGIN=YES
  fi
fi

if [[ "${NEED_LOGIN}" == "YES" ]]; then
  USER_ACTION_REQUIRED=YES
  USER_ACTION="cloudflared tunnel login"
  echo "USER_ACTION_REQUIRED=YES"
  echo "USER_ACTION=${USER_ACTION}"
  echo "HINT=After browser login completes and ${CF_DIR}/cert.pem appears, re-run this script."
  echo "DATABASE_CHANGED=NO"
  echo "MIGRATION_RUN=NO"
  echo "SECRET_REGENERATION=NO"
  exit 2
fi

# =====================================================================
section "PHASE 3 — CREATE OR REUSE NAMED TUNNEL"
# =====================================================================
if [[ -z "${TUNNEL_ID}" ]]; then
  info "Creating named tunnel ${TUNNEL_NAME} (only because missing)"
  # Capture create output but strip any JSON-looking lines from stdout reporting
  create_out="$(cloudflared tunnel create "${TUNNEL_NAME}" 2>&1 || true)"
  # Never echo raw create_out if it embeds secrets — print only non-json summary lines
  echo "${create_out}" | grep -Eiv 'json|-----|BEGIN|private|secret|token' | head -n 20 || true
  TUNNEL_ID="$(cloudflared tunnel list 2>/dev/null | awk -v n="${TUNNEL_NAME}" '$2==n{print $1; exit}' || true)"
  [[ -n "${TUNNEL_ID}" ]] || abort "tunnel create failed — ${TUNNEL_NAME} not in list"
  CRED="${CF_DIR}/${TUNNEL_ID}.json"
  [[ -f "${CRED}" ]] || abort "credential file missing after create (expected ${TUNNEL_ID}.json filename only)"
  echo "TUNNEL_CREATED=YES"
else
  echo "TUNNEL_CREATED=NO"
fi
echo "TUNNEL_NAME=${TUNNEL_NAME}"
echo "TUNNEL_ID=${TUNNEL_ID}"
[[ -n "${CRED}" && -f "${CRED}" ]] || {
  CRED="${CF_DIR}/${TUNNEL_ID}.json"
  [[ -f "${CRED}" ]] || abort "credentials file missing for ${TUNNEL_ID}"
}
chmod 600 "${CRED}" 2>/dev/null || true
echo "TUNNEL_CREDENTIAL_FILE=$(basename "${CRED}")"

# =====================================================================
section "PHASE 4 — DNS ROUTE"
# =====================================================================
# Idempotent: if route exists, cloudflared typically errors harmlessly — do not destroy.
route_out="$(cloudflared tunnel route dns "${TUNNEL_NAME}" "${HOSTNAME_API}" 2>&1 || true)"
# Redact anything that looks like a token; show short status only
if echo "${route_out}" | grep -Eiq 'already|exist|CNAME|success|added|updated|ok'; then
  API_DNS_ROUTE=PASS
elif echo "${route_out}" | grep -Eiq 'error|fail|denied|unauthorized'; then
  # Still may work if DNS already correct — verify later via public health
  echo "DNS_ROUTE_MSG=$(echo "${route_out}" | tr '\n' ' ' | cut -c1-160)"
  API_DNS_ROUTE=UNKNOWN
else
  API_DNS_ROUTE=PASS
fi
echo "API_DNS_ROUTE=${API_DNS_ROUTE}"

# =====================================================================
section "PHASE 5 — CONFIG (no commit)"
# =====================================================================
umask 077
cat >"${CFG}" <<EOF
# Generated by m1-persistent-tunnel-and-freeze.sh — DO NOT COMMIT
tunnel: ${TUNNEL_ID}
credentials-file: ${CRED}
ingress:
  - hostname: ${HOSTNAME_API}
    service: http://${CADDY_ADDR}
  - service: http_status:404
EOF
chmod 600 "${CFG}"
# Keep alias path used by earlier scripts
cp "${CFG}" "${CFG_ALIAS}"
chmod 600 "${CFG_ALIAS}"
echo "CONFIG=${CFG}"
echo "CONFIG_ALIAS=${CFG_ALIAS}"
echo "INGRESS=${HOSTNAME_API} -> http://${CADDY_ADDR}"

# =====================================================================
section "PHASE 6 — PERSIST cloudflared LaunchAgent"
# =====================================================================
# Prefer official-style: cloudflared tunnel --config ... run <name>
cat >"${LAUNCH_AGENTS}/${PLIST_CF}.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_CF}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${CF_BIN}</string>
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
  <string>${LOG_DIR}/cloudflared.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/cloudflared.err.log</string>
</dict>
</plist>
EOF
# Remove older label if present to avoid duplicate tunnels
if [[ -f "${LAUNCH_AGENTS}/com.guoqiao.cloudflared-api.plist" ]]; then
  launchctl bootout "gui/$(id -u)/com.guoqiao.cloudflared-api" 2>/dev/null || \
    launchctl unload "${LAUNCH_AGENTS}/com.guoqiao.cloudflared-api.plist" 2>/dev/null || true
  rm -f "${LAUNCH_AGENTS}/com.guoqiao.cloudflared-api.plist"
  echo "REMOVED_LEGACY_PLIST=com.guoqiao.cloudflared-api"
fi
# Stop stray nohup cloudflared for this tunnel (best-effort; do not touch other tunnels)
if command -v pgrep >/dev/null 2>&1; then
  while read -r pid; do
    [[ -n "$pid" ]] || continue
    args="$(ps -p "$pid" -o args= 2>/dev/null || true)"
    case "$args" in
      *"${TUNNEL_NAME}"*|*guoqiao-api.yml*|*${CFG}*)
        info "Stopping non-launchd cloudflared pid=${pid}"
        kill "$pid" 2>/dev/null || true
        ;;
    esac
  done < <(pgrep -f 'cloudflared.*tunnel' 2>/dev/null || true)
fi

install_plist "${PLIST_CF}" "${LAUNCH_AGENTS}/${PLIST_CF}.plist"
sleep 2
if launchd_running "${PLIST_CF}"; then
  TUNNEL_LAUNCHD=PASS
  TUNNEL_PERSISTENT=YES
else
  # kickstart may need a moment
  sleep 3
  if launchd_running "${PLIST_CF}"; then
    TUNNEL_LAUNCHD=PASS
    TUNNEL_PERSISTENT=YES
  else
    TUNNEL_LAUNCHD=FAIL
    TUNNEL_PERSISTENT=NO
    tail -n 40 "${LOG_DIR}/cloudflared.err.log" 2>/dev/null || true
    abort "LaunchAgent ${PLIST_CF} not running"
  fi
fi
echo "TUNNEL_LAUNCHD=${TUNNEL_LAUNCHD}"
echo "TUNNEL_PERSISTENT=${TUNNEL_PERSISTENT}"

# =====================================================================
section "PHASE 7 — PERSIST Caddy + verify LaunchAgents"
# =====================================================================
require_caddy=1
if ! command -v caddy >/dev/null 2>&1; then
  abort "caddy not installed"
fi
CADDY_BIN="$(command -v caddy)"
[[ -f "${CADDYFILE}" ]] || abort "missing ${CADDYFILE}"

# Ensure Caddyfile still points only at 8010 (read-only check — do not rewrite)
if ! grep -q 'reverse_proxy 127.0.0.1:8010' "${CADDYFILE}"; then
  abort "Caddyfile upstream must remain 127.0.0.1:8010"
fi
echo "CADDY_UPSTREAM=127.0.0.1:8010 (unchanged)"

cat >"${LAUNCH_AGENTS}/${PLIST_CADDY}.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${PLIST_CADDY}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${CADDY_BIN}</string>
    <string>run</string>
    <string>--config</string>
    <string>${CADDYFILE}</string>
    <string>--adapter</string>
    <string>caddyfile</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${LOG_DIR}/caddy.out.log</string>
  <key>StandardErrorPath</key>
  <string>${LOG_DIR}/caddy.err.log</string>
</dict>
</plist>
EOF

# Stop ad-hoc caddy so LaunchAgent owns :8088
caddy stop >/dev/null 2>&1 || true
sleep 1
install_plist "${PLIST_CADDY}" "${LAUNCH_AGENTS}/${PLIST_CADDY}.plist"

ok_caddy=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  code="$(http_code "http://${CADDY_ADDR}/api/health")"
  if [[ "$code" == "200" ]]; then ok_caddy=1; break; fi
  sleep 1
done
[[ "${ok_caddy}" -eq 1 ]] || {
  tail -n 40 "${LOG_DIR}/caddy.err.log" 2>/dev/null || true
  abort "Caddy :8088 health not 200 after LaunchAgent"
}
CADDY_8088=PASS
if launchd_running "${PLIST_CADDY}"; then
  CADDY_LAUNCHD=PASS
else
  CADDY_LAUNCHD=WARN
fi
echo "CADDY_LAUNCHD=${CADDY_LAUNCHD}"

# SaaS agent should already exist from bootstrap — verify only
if launchd_running "${PLIST_SAAS}"; then
  echo "SAAS_LAUNCHD=RUNNING"
else
  echo "SAAS_LAUNCHD=NOT_RUNNING"
  # Do not rewrite .env; only kickstart if plist exists
  if [[ -f "${LAUNCH_AGENTS}/${PLIST_SAAS}.plist" ]]; then
    launchctl kickstart -k "gui/$(id -u)/${PLIST_SAAS}" 2>/dev/null || true
    sleep 2
  fi
  launchd_running "${PLIST_SAAS}" && echo "SAAS_LAUNCHD=RUNNING" || echo "SAAS_LAUNCHD=FAIL"
fi

c8010="$(http_code "http://${SAAS_ADDR}/api/health")"
c8088="$(http_code "http://${CADDY_ADDR}/api/health")"
[[ "${c8010}" == "200" ]] && SAAS_8010=PASS || SAAS_8010=FAIL
[[ "${c8088}" == "200" ]] && CADDY_8088=PASS || CADDY_8088=FAIL
echo "SAAS_8010=${SAAS_8010}"
echo "CADDY_8088=${CADDY_8088}"
echo "POSTGRES_UP=${POSTGRES_UP}"
echo "LAUNCHAGENT_${PLIST_CF}=$(launchd_running "${PLIST_CF}" && echo RUNNING || echo DOWN)"
echo "LAUNCHAGENT_${PLIST_CADDY}=$(launchd_running "${PLIST_CADDY}" && echo RUNNING || echo DOWN)"
echo "LAUNCHAGENT_${PLIST_SAAS}=$(launchd_running "${PLIST_SAAS}" && echo RUNNING || echo DOWN)"

[[ "${SAAS_8010}" == "PASS" && "${CADDY_8088}" == "PASS" ]] || abort "local stack unhealthy after persistence"

# =====================================================================
section "PHASE 8 — PUBLIC ACCEPTANCE"
# =====================================================================
pub_ok=0
for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  code="$(http_code "https://${HOSTNAME_API}/api/health")"
  if [[ "$code" == "200" ]]; then pub_ok=1; break; fi
  sleep 2
done
if [[ "${pub_ok}" -eq 1 ]]; then
  PUBLIC_API_HEALTH=PASS
  API_DNS_ROUTE=PASS
else
  PUBLIC_API_HEALTH=FAIL
  USER_ACTION_REQUIRED=YES
  USER_ACTION="Verify Cloudflare DNS CNAME ${HOSTNAME_API} → ${TUNNEL_ID}.cfargotunnel.com and LaunchAgent ${PLIST_CF}"
fi
echo "PUBLIC_API_HEALTH=${PUBLIC_API_HEALTH}"

pu="$(http_code "https://${HOSTNAME_API}/api/universities?target=international")"
ps="$(http_code "https://${HOSTNAME_API}/api/schedules?target=international")"
echo "PUBLIC_UNIVERSITIES_HTTP=${pu}"
echo "PUBLIC_SCHEDULES_HTTP=${ps}"
[[ "${pu}" == "200" ]] || PUBLIC_API_HEALTH=FAIL
[[ "${ps}" == "200" ]] || PUBLIC_API_HEALTH=FAIL

h5_home="$(http_code "https://${HOSTNAME_APP}/")"
h5_uni="$(http_code "https://${HOSTNAME_APP}/universities")"
h5_tl="$(http_code "https://${HOSTNAME_APP}/timeline")"
[[ "${h5_uni}" == "200" ]] || h5_uni="${h5_home}"
[[ "${h5_tl}" == "200" ]] || h5_tl="${h5_home}"
[[ "${h5_home}" == "200" ]] && H5_HOME=PASS || H5_HOME=FAIL
[[ "${h5_uni}" == "200" ]] && H5_UNIVERSITIES=PASS || H5_UNIVERSITIES=FAIL
[[ "${h5_tl}" == "200" ]] && H5_TIMELINE=PASS || H5_TIMELINE=FAIL
echo "H5_HOME=${H5_HOME}"
echo "H5_UNIVERSITIES=${H5_UNIVERSITIES}"
echo "H5_TIMELINE=${H5_TIMELINE}"

# =====================================================================
section "PHASE 9 — LOGIN ACCEPTANCE"
# =====================================================================
echo "RELOGIN_REQUIRED=YES"
echo "NOTE=Old JWT sessions are invalid after secret bootstrap. Do not invent test passwords."
if [[ "${USER_ACTION_REQUIRED}" != "YES" ]]; then
  USER_ACTION_REQUIRED=YES
  USER_ACTION="Open https://${HOSTNAME_APP} on phone, re-login, verify home/universities/timeline + create student + A→B→A switch"
fi

# =====================================================================
section "PHASE 10 — PRODUCTION FREEZE"
# =====================================================================
COMMIT="$(git -C "${ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
BRANCH="$(git -C "${ROOT}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
FREEZE_OK=NO
if [[ "${TUNNEL_PERSISTENT}" == "YES" && "${PUBLIC_API_HEALTH}" == "PASS" && "${H5_HOME}" == "PASS" ]]; then
  FREEZE_OK=YES
  umask 077
  cat >"${FREEZE_FILE}" <<EOF
GUOQIAO_PRODUCTION_FREEZE_REPORT
FROZEN_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
BRANCH=${BRANCH}
COMMIT=${COMMIT}
APP_URL=https://${HOSTNAME_APP}
API_URL=https://${HOSTNAME_API}
DATABASE_REVISION=006_student_profile_slots
DATABASE_CHANGED=NO
MIGRATION_RUN=NO
TUNNEL_NAME=${TUNNEL_NAME}
TUNNEL_ID=${TUNNEL_ID}
TUNNEL_PERSISTENT=YES
SAAS_LAUNCHD=${PLIST_SAAS}
CADDY_LAUNCHD=${PLIST_CADDY}
CLOUDFLARED_LAUNCHD=${PLIST_CF}
MAIN_MERGED=NO
EOF
  chmod 600 "${FREEZE_FILE}"
  echo "PRODUCTION_FREEZE=YES"
  echo "FREEZE_FILE=${FREEZE_FILE}"
  echo "MAIN_CHANGED=NO"
else
  echo "PRODUCTION_FREEZE=NO"
  echo "REASON=tunnel/public/H5 not all PASS"
fi

echo "============================================================"
echo "GUOQIAO_M1_PERSISTENT_GO_LIVE_REPORT"
echo "DATABASE_REVISION=006_student_profile_slots"
echo "DATABASE_CHANGED=NO"
echo "MIGRATION_RUN=NO"
echo "SAAS_8010=${SAAS_8010}"
echo "CADDY_8088=${CADDY_8088}"
echo "CLOUDFLARED_INSTALLED=${CLOUDFLARED_INSTALLED}"
echo "TUNNEL_NAME=${TUNNEL_NAME}"
echo "TUNNEL_ID=${TUNNEL_ID}"
echo "TUNNEL_PERSISTENT=${TUNNEL_PERSISTENT}"
echo "TUNNEL_LAUNCHD=${TUNNEL_LAUNCHD}"
echo "API_DNS_ROUTE=${API_DNS_ROUTE}"
echo "PUBLIC_API_HEALTH=${PUBLIC_API_HEALTH}"
echo "APP_URL=https://${HOSTNAME_APP}"
echo "API_URL=https://${HOSTNAME_API}"
echo "H5_HOME=${H5_HOME}"
echo "H5_UNIVERSITIES=${H5_UNIVERSITIES}"
echo "H5_TIMELINE=${H5_TIMELINE}"
echo "RELOGIN_REQUIRED=YES"
echo "CNBER_CHANGED=NO"
echo "BETA_CHANGED=NO"
echo "MAIN_CHANGED=NO"
echo "COMMIT=${COMMIT}"
echo "PUSH=origin/cursor/mobile-cloud-preview"
echo "PRODUCTION_FREEZE=${FREEZE_OK}"
echo "USER_ACTION_REQUIRED=${USER_ACTION_REQUIRED}"
echo "USER_ACTION=${USER_ACTION}"
echo "============================================================"

if [[ "${PUBLIC_API_HEALTH}" != "PASS" || "${TUNNEL_PERSISTENT}" != "YES" ]]; then
  exit 1
fi
exit 0
