#!/usr/bin/env bash
# LaunchAgent / manual wrapper: start SaaS uvicorn on 127.0.0.1:8010
# Uses discovered runtime only — never Homebrew system site-packages.
set -euo pipefail

STATE_DIR="${HOME}/.guoqiao/saas"
RUNTIME_ENV="${STATE_DIR}/runtime.env"
LOG_DIR="${STATE_DIR}/logs"
mkdir -p "$LOG_DIR"

if [[ ! -f "$RUNTIME_ENV" ]]; then
  echo "ERROR: missing ${RUNTIME_ENV} — run: bash deploy/api/m1-saas-runtime-recover.sh" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$RUNTIME_ENV"

: "${SAAS_BACKEND_DIR:?}"
: "${SAAS_PYTHON:?}"

cd "$SAAS_BACKEND_DIR"
# app.config.Settings loads .env from WorkingDirectory — do not shell-source secrets.

exec "$SAAS_PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port 8010
