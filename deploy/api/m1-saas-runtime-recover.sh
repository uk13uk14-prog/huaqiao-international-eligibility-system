#!/usr/bin/env bash
# ONE_SHOT (M1): discover original SaaS Python/venv → restore :8010 → LaunchAgent → m1-go-live
# Does NOT: sudo pip / brew global deps / invent DATABASE_URL / touch CNber / merge main / stash pop
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
STATE_DIR="${HOME}/.guoqiao/saas"
RUNTIME_ENV="${STATE_DIR}/runtime.env"
LOG_DIR="${STATE_DIR}/logs"
LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"
PLIST_LABEL="com.guoqiao.saas-backend"
PLIST_PATH="${LAUNCH_AGENTS}/${PLIST_LABEL}.plist"
RUN_WRAPPER="${ROOT}/deploy/api/m1-saas-backend-run.sh"
SKIP_GO_LIVE="${SKIP_GO_LIVE:-0}"
ALLOW_CREATE_VENV="${ALLOW_CREATE_VENV:-1}"

mkdir -p "$STATE_DIR" "$LOG_DIR" "$LAUNCH_AGENTS"

echo "============================================================"
echo "GUOQIAO M1 SaaS Runtime Recovery"
echo "ROOT=${ROOT}"
echo "BACKEND=${BACKEND}"
echo "HEAD=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
echo "============================================================"

die() { echo "ERROR: $*" >&2; exit 1; }
info() { echo "==> $*"; }
mask_url() {
  # redact password in URLs for logs
  sed -E 's#(://[^:/@]+:)[^@]+@#\1***@#g'
}

can_import_saas() {
  local py="$1"
  [[ -x "$py" ]] || return 1
  "$py" -c "import fastapi,uvicorn,sqlalchemy,pydantic_settings" >/dev/null 2>&1
}

# ---------- Phase 1: discover Python / venv ----------
info "Phase 1 — discover SaaS Python / venv (no system pip install)"

# bash 3.2 (macOS /bin/bash) safe candidate list
CANDIDATES=""
add_cand() {
  local p="$1"
  local c
  [[ -n "$p" ]] || return 0
  [[ -e "$p" ]] || return 0
  # resolve symlinks when possible
  if command -v realpath >/dev/null 2>&1; then
    p="$(realpath "$p" 2>/dev/null || echo "$p")"
  elif command -v python3 >/dev/null 2>&1; then
    p="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$p" 2>/dev/null || echo "$p")"
  fi
  old_ifs="$IFS"
  IFS='|'
  # shellcheck disable=SC2086
  for c in $CANDIDATES; do
    [[ "$c" == "$p" ]] && { IFS="$old_ifs"; return 0; }
  done
  IFS="$old_ifs"
  if [[ -z "$CANDIDATES" ]]; then
    CANDIDATES="$p"
  else
    CANDIDATES="${CANDIDATES}|${p}"
  fi
}

# Project-local venvs (preferred)
add_cand "${BACKEND}/.venv/bin/python"
add_cand "${BACKEND}/.venv/bin/python3"
add_cand "${BACKEND}/venv/bin/python"
add_cand "${ROOT}/huaqiao-saas-pro/.venv/bin/python"
add_cand "${ROOT}/.venv/bin/python"

# Existing LaunchAgent ProgramArguments
if [[ -f "$PLIST_PATH" ]]; then
  while IFS= read -r line; do
    case "$line" in
      */python*|*/Python*) add_cand "$line" ;;
    esac
  done < <(plutil -extract ProgramArguments xml1 -o - "$PLIST_PATH" 2>/dev/null | sed -n 's/.*<string>\(.*\)<\/string>.*/\1/p' || true)
fi
# Any guoqiao/huaqiao/saas launch agents
for f in "${LAUNCH_AGENTS}"/com.guoqiao.*.plist "${LAUNCH_AGENTS}"/*huaqiao*.plist "${LAUNCH_AGENTS}"/*saas*.plist; do
  [[ -f "$f" ]] || continue
  while IFS= read -r line; do
    case "$line" in
      */python*|*/Python*|*uvicorn*) add_cand "$line" ;;
    esac
  done < <(plutil -extract ProgramArguments xml1 -o - "$f" 2>/dev/null | sed -n 's/.*<string>\(.*\)<\/string>.*/\1/p' || true)
done

# Shell history: absolute python path before uvicorn app.main
for hist in "${HOME}/.zsh_history" "${HOME}/.bash_history" "${HOME}/.history"; do
  [[ -f "$hist" ]] || continue
  while IFS= read -r line; do
    # examples: /path/.venv/bin/python -m uvicorn app.main:app --port 8010
    if [[ "$line" == *uvicorn*app.main* ]] || [[ "$line" == *uvicorn* && "$line" == *8010* ]]; then
      tok="$(echo "$line" | awk '{for(i=1;i<=NF;i++) if($i ~ /python/) {print $i; exit}}')"
      case "$tok" in
        /*) add_cand "$tok" ;;
      esac
      # also: source .venv && python -m uvicorn  → look for cd .../backend nearby (skip)
      if [[ "$line" == *".venv/bin/python"* ]]; then
        add_cand "$(echo "$line" | grep -oE '[^ ]+\.venv/bin/python[0-9.]*' | head -1)"
      fi
    fi
  done < <(grep -E 'uvicorn|8010' "$hist" 2>/dev/null | tail -n 80 || true)
done

# Nearby venvs under home (bounded)
while IFS= read -r p; do
  add_cand "$p"
done < <(find "$HOME" -maxdepth 6 \( -path '*/huaqiao*/.venv/bin/python' -o -path '*/saas*/.venv/bin/python' -o -path '*/guoqiao*/.venv/bin/python' \) 2>/dev/null | head -n 40 || true)

# pyenv
if [[ -d "${HOME}/.pyenv/versions" ]]; then
  while IFS= read -r p; do
    add_cand "$p"
  done < <(find "${HOME}/.pyenv/versions" -maxdepth 4 -type f -name python 2>/dev/null | head -n 20 || true)
fi

# conda
if command -v conda >/dev/null 2>&1; then
  while IFS= read -r p; do
    add_cand "${p}/bin/python"
  done < <(conda env list 2>/dev/null | awk '/^\S/ && !/^#/ {print $NF}' | head -n 20 || true)
fi

# docker (informational; we prefer host venv for :8010)
DOCKER_SAAS=NO
if command -v docker >/dev/null 2>&1; then
  if docker ps -a --format '{{.Names}} {{.Ports}}' 2>/dev/null | grep -Ei 'saas|8010|huaqiao' >/dev/null; then
    DOCKER_SAAS=YES
    info "Docker containers mentioning saas/8010 found (will not auto-use unless host runtime missing)"
  fi
fi

SAAS_PYTHON=""
SAAS_VENV=""
OLD_RUNTIME_FOUND=NO
old_ifs="$IFS"
IFS='|'
# shellcheck disable=SC2086
for py in $CANDIDATES; do
  IFS="$old_ifs"
  [[ -n "$py" ]] || continue
  if can_import_saas "$py"; then
    SAAS_PYTHON="$py"
    OLD_RUNTIME_FOUND=YES
    case "$py" in
      */.venv/bin/*|*/venv/bin/*) SAAS_VENV="$(cd "$(dirname "$py")/.." && pwd)" ;;
    esac
    info "FOUND working Python: ${SAAS_PYTHON}"
    break
  fi
  IFS='|'
done
IFS="$old_ifs"

CREATED_VENV=NO
if [[ -z "$SAAS_PYTHON" ]]; then
  if [[ "$ALLOW_CREATE_VENV" != "1" ]]; then
    die "No working SaaS Python found and ALLOW_CREATE_VENV=0"
  fi
  info "No existing venv with fastapi/uvicorn — creating ${BACKEND}/.venv (isolated; not system Python)"
  # Bootstrap interpreter: prefer python3.11, then 3.12, then python3 — ONLY to create venv
  BOOTSTRAP=""
  for b in /opt/homebrew/bin/python3.11 /usr/local/bin/python3.11 \
           /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 \
           /opt/homebrew/bin/python3 /usr/local/bin/python3 \
           "$(command -v python3.11 2>/dev/null || true)" \
           "$(command -v python3.12 2>/dev/null || true)" \
           "$(command -v python3 2>/dev/null || true)"; do
    [[ -n "$b" && -x "$b" ]] || continue
    if "$b" -c "import venv" >/dev/null 2>&1; then
      BOOTSTRAP="$b"
      break
    fi
  done
  [[ -n "$BOOTSTRAP" ]] || die "No bootstrap python with venv module"
  info "BOOTSTRAP_PYTHON=${BOOTSTRAP} (used only to create .venv)"
  "$BOOTSTRAP" -m venv "${BACKEND}/.venv"
  SAAS_PYTHON="${BACKEND}/.venv/bin/python"
  SAAS_VENV="${BACKEND}/.venv"
  # shellcheck disable=SC1091
  source "${BACKEND}/.venv/bin/activate"
  pip install -U pip setuptools wheel
  # Prefer documented SaaS requirements.txt (full deps); locked is Docker/CI subset
  if [[ -f "${BACKEND}/requirements.txt" ]]; then
    pip install -r "${BACKEND}/requirements.txt"
  fi
  if [[ -f "${BACKEND}/requirements-locked.txt" ]]; then
    # Ensure CI-locked pins present without wiping extras if already installed
    pip install -r "${BACKEND}/requirements-locked.txt" || true
  fi
  can_import_saas "$SAAS_PYTHON" || die "Fresh .venv still cannot import fastapi/uvicorn/sqlalchemy"
  CREATED_VENV=YES
  OLD_RUNTIME_FOUND=NO
  info "Created isolated venv OK"
fi

# Derive venv if not set
if [[ -z "$SAAS_VENV" ]]; then
  case "$SAAS_PYTHON" in
    */.venv/bin/*|*/venv/bin/*) SAAS_VENV="$(cd "$(dirname "$SAAS_PYTHON")/.." && pwd)" ;;
    *) SAAS_VENV="(none — interpreter ${SAAS_PYTHON})" ;;
  esac
fi

# ---------- Phase 2: env / database source (never invent production DB) ----------
info "Phase 2 — locate env / database source (will NOT overwrite existing .env)"

ENV_SOURCE="none"
DATABASE_SOURCE="unknown"
ENV_FILE=""

# Prefer existing backend .env
if [[ -f "${BACKEND}/.env" ]]; then
  ENV_FILE="${BACKEND}/.env"
  ENV_SOURCE="backend/.env"
elif [[ -f "${BACKEND}/.env.local" ]]; then
  ENV_FILE="${BACKEND}/.env.local"
  ENV_SOURCE="backend/.env.local"
else
  # Search nearby (do not copy yet — report)
  for cand in \
    "${ROOT}/.env" \
    "${ROOT}/huaqiao-saas-pro/.env" \
    "${HOME}/.guoqiao/saas/.env" \
    "${HOME}/.config/guoqiao/saas.env" \
    "${STATE_DIR}/.env.recovered"; do
    if [[ -f "$cand" ]]; then
      ENV_FILE="$cand"
      ENV_SOURCE="found:${cand}"
      break
    fi
  done
fi

# LaunchAgent EnvironmentVariables
if [[ -z "$ENV_FILE" && -f "$PLIST_PATH" ]]; then
  if plutil -extract EnvironmentVariables xml1 -o /tmp/gq-la-env.xml "$PLIST_PATH" 2>/dev/null; then
    ENV_SOURCE="launchd:${PLIST_PATH}"
  fi
fi

# If we found a non-backend env file with DATABASE_URL, symlink/copy ONLY if backend .env missing
if [[ ! -f "${BACKEND}/.env" && -n "$ENV_FILE" && "$ENV_FILE" != "${BACKEND}/.env" ]]; then
  if grep -qE '^[[:space:]]*DATABASE_URL=' "$ENV_FILE" 2>/dev/null; then
    info "Restoring backend/.env from ${ENV_FILE} (no overwrite of secrets elsewhere)"
    cp "$ENV_FILE" "${BACKEND}/.env"
    ENV_SOURCE="restored_from:${ENV_FILE}"
    ENV_FILE="${BACKEND}/.env"
  fi
fi

# Parse DATABASE_URL without printing secrets
if [[ -f "${BACKEND}/.env" ]]; then
  DB_URL_LINE="$(grep -E '^[[:space:]]*DATABASE_URL=' "${BACKEND}/.env" | tail -n1 || true)"
  if [[ -n "$DB_URL_LINE" ]]; then
    DB_VAL="${DB_URL_LINE#*=}"
    DB_VAL="${DB_VAL%\"}"
    DB_VAL="${DB_VAL#\"}"
    case "$DB_VAL" in
      sqlite*) DATABASE_SOURCE="sqlite(from .env)" ;;
      postgres*|postgresql*) DATABASE_SOURCE="postgres(from .env)" ;;
      *) DATABASE_SOURCE="custom(from .env)" ;;
    esac
    echo "DATABASE_URL_MASKED=$(echo "$DB_VAL" | mask_url)"
  fi
fi

# Default sqlite fallback is BLOCKED for production recovery.
# Prefer postgres via .env; never create empty saas_pro.db.
if [[ "$DATABASE_SOURCE" == "unknown" ]]; then
  if [[ -f "${BACKEND}/saas_pro.db" ]]; then
    DATABASE_SOURCE="sqlite_existing_file_only (still requires DATABASE_URL in .env for guard PASS)"
    info "Found existing saas_pro.db — still need explicit DATABASE_URL in .env to start"
  else
    DATABASE_SOURCE="MISSING"
    info "No .env DATABASE_URL and no saas_pro.db"
  fi
fi

# History hint for DATABASE_URL (do not write automatically if ambiguous)
if [[ ! -f "${BACKEND}/.env" ]]; then
  for hist in "${HOME}/.zsh_history" "${HOME}/.bash_history"; do
    [[ -f "$hist" ]] || continue
    if grep -q 'DATABASE_URL=' "$hist" 2>/dev/null; then
      info "History contains DATABASE_URL=… — if production used Postgres, restore that into backend/.env before continuing"
      ENV_SOURCE="${ENV_SOURCE};history_mentions_DATABASE_URL"
      break
    fi
  done
fi

info "PRODUCTION_DB_GUARD (FAIL CLOSED — no empty sqlite)"
if ! bash "${ROOT}/deploy/api/production-db-guard.sh" "$BACKEND"; then
  echo "ERROR: Refusing to start SaaS without confirmed DATABASE_URL/.env"
  echo "HINT: bash deploy/api/m1-db-source-discover.sh"
  echo "HINT: Only after DATABASE_SOURCE_CONFIRMED=YES, restore backend/.env (separate step — not auto)."
  exit 1
fi

# ---------- Phase 3: write runtime state + LaunchAgent ----------
info "Phase 3 — persist runtime + install LaunchAgent ${PLIST_LABEL}"

cat >"$RUNTIME_ENV" <<EOF
# Generated by m1-saas-runtime-recover.sh — do not commit
SAAS_BACKEND_DIR=${BACKEND}
SAAS_PYTHON=${SAAS_PYTHON}
SAAS_VENV=${SAAS_VENV}
SAAS_START_METHOD=launchd:${PLIST_LABEL}
EOF

chmod +x "$RUN_WRAPPER"

# Unload existing agent if present
launchctl bootout "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || \
  launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Stop anything currently on 8010 that looks like uvicorn (not CNber)
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -nP -iTCP:8010 -sTCP:LISTEN -t 2>/dev/null || true)"
  if [[ -n "$PIDS" ]]; then
    for pid in $PIDS; do
      cmd="$(ps -p "$pid" -o args= 2>/dev/null || true)"
      case "$cmd" in
        *uvicorn*|*app.main*|*huaqiao-saas*)
          info "Stopping old :8010 pid=${pid}"
          kill "$pid" 2>/dev/null || true
          sleep 1
          kill -9 "$pid" 2>/dev/null || true
          ;;
        *)
          info "WARN: :8010 held by non-saas process; not killing: ${cmd}"
          ;;
      esac
    done
  fi
fi

cat >"$PLIST_PATH" <<EOF
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

launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH" 2>/dev/null || launchctl load -w "$PLIST_PATH"
# kickstart
launchctl kickstart -k "gui/$(id -u)/${PLIST_LABEL}" 2>/dev/null || true

SAAS_START_METHOD="launchd:${PLIST_LABEL}"
AUTO_START_CONFIGURED=YES

# ---------- Phase 4: wait for health ----------
info "Phase 4 — wait for :8010 health"
OK=0
i=0
while [[ $i -lt 30 ]]; do
  i=$((i + 1))
  code="$(curl -sS -o /tmp/gq-saas-health.json -w '%{http_code}' http://127.0.0.1:8010/api/health || echo 000)"
  if [[ "$code" == "200" ]]; then
    OK=1
    break
  fi
  sleep 1
done

if [[ "$OK" != "1" ]]; then
  echo "---- saas-backend.err.log (tail) ----"
  tail -n 80 "${LOG_DIR}/saas-backend.err.log" 2>/dev/null || true
  echo "---- saas-backend.out.log (tail) ----"
  tail -n 40 "${LOG_DIR}/saas-backend.out.log" 2>/dev/null || true
  die "PORT_8010 did not become healthy (last HTTP=${code:-000})"
fi

code_students="$(curl -sS -o /tmp/gq-students.json -w '%{http_code}' http://127.0.0.1:8010/api/students || echo 000)"
code_meta="$(curl -sS -o /tmp/gq-students-meta.json -w '%{http_code}' http://127.0.0.1:8010/api/students/meta || echo 000)"

echo "PORT_8010=UP"
echo "HEALTH_8010=${code:-200}"
echo "STUDENTS_8010=${code_students}"
echo "STUDENTS_META_8010=${code_meta}"

[[ "${code:-200}" == "200" ]] || die "health not 200"
[[ "$code_students" == "401" || "$code_students" == "403" ]] || die "students expected 401/403, got ${code_students}"
[[ "$code_meta" == "200" ]] || die "students/meta expected 200, got ${code_meta}"

# ---------- Phase 5: go-live ----------
M1_GO_LIVE=SKIPPED
if [[ "$SKIP_GO_LIVE" == "1" ]]; then
  info "SKIP_GO_LIVE=1 — not running m1-go-live.sh"
else
  info "Phase 5 — bash deploy/api/m1-go-live.sh"
  if bash "${ROOT}/deploy/api/m1-go-live.sh"; then
    M1_GO_LIVE=PASS
  else
    M1_GO_LIVE=FAIL
  fi
fi

echo "============================================================"
echo "GUOQIAO_M1_SAAS_RUNTIME_RECOVERY_SUMMARY"
echo "ROOT_CAUSE=wrong_interpreter(Homebrew python without project deps)"
echo "OLD_RUNTIME_FOUND=${OLD_RUNTIME_FOUND}"
echo "CREATED_VENV=${CREATED_VENV}"
echo "SAAS_PYTHON=${SAAS_PYTHON}"
echo "SAAS_VENV=${SAAS_VENV}"
echo "SAAS_START_METHOD=${SAAS_START_METHOD}"
echo "ENV_SOURCE=${ENV_SOURCE}"
echo "DATABASE_SOURCE=${DATABASE_SOURCE}"
echo "SYSTEM_PYTHON_MODIFIED=NO"
echo "PORT_8010=UP"
echo "HEALTH_8010=200"
echo "STUDENTS_8010=${code_students}"
echo "STUDENTS_META_8010=${code_meta}"
echo "AUTO_START_CONFIGURED=${AUTO_START_CONFIGURED}"
echo "AUTO_START_METHOD=${SAAS_START_METHOD}"
echo "M1_GO_LIVE=${M1_GO_LIVE}"
echo "DOCKER_SAAS_SEEN=${DOCKER_SAAS}"
echo "RUNTIME_ENV=${RUNTIME_ENV}"
echo "PLIST_PATH=${PLIST_PATH}"
echo "LOG_DIR=${LOG_DIR}"
echo "============================================================"

if [[ "$M1_GO_LIVE" == "FAIL" ]]; then
  exit 1
fi
exit 0
