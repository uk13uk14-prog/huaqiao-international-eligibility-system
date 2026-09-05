#!/usr/bin/env bash
# Shared production DB guard — FAIL CLOSED.
# Refuses to start SaaS backend without a confirmed non-empty DB source.
# Never creates sqlite / never invents DATABASE_URL.
#
# Usage:
#   bash deploy/api/production-db-guard.sh <backend_dir>
# Exit 0 = OK to start; Exit 1 = blocked.
set -u

BACKEND_DIR="${1:-}"
if [[ -z "${BACKEND_DIR}" ]]; then
  echo "PRODUCTION_DB_GUARD=ENABLED"
  echo "GUARD_RESULT=FAIL"
  echo "GUARD_REASON=missing_backend_dir_arg"
  exit 1
fi

echo "PRODUCTION_DB_GUARD=ENABLED"
echo "EMPTY_SQLITE_FALLBACK_BLOCKED=YES"

ENV_FILE=""
if [[ -f "${BACKEND_DIR}/.env" ]]; then
  ENV_FILE="${BACKEND_DIR}/.env"
elif [[ -f "${BACKEND_DIR}/.env.local" ]]; then
  ENV_FILE="${BACKEND_DIR}/.env.local"
fi

DB_URL=""
if [[ -n "${ENV_FILE}" ]]; then
  # shellcheck disable=SC2002
  line="$(grep -E '^[[:space:]]*DATABASE_URL=' "${ENV_FILE}" 2>/dev/null | tail -n1 || true)"
  if [[ -n "${line}" ]]; then
    DB_URL="${line#*=}"
    DB_URL="${DB_URL%\"}"
    DB_URL="${DB_URL#\"}"
    DB_URL="${DB_URL%\'}"
    DB_URL="${DB_URL#\'}"
  fi
fi

# Also accept already-exported DATABASE_URL (LaunchAgent / shell) without printing it.
if [[ -z "${DB_URL}" && -n "${DATABASE_URL:-}" ]]; then
  DB_URL="${DATABASE_URL}"
fi

redact_url() {
  echo "$1" | sed -E 's#(://[^:/@]+:)[^@/]+@#\1***@#g; s#(password=)[^&]+#\1***#gi'
}

if [[ -z "${DB_URL}" ]]; then
  echo "GUARD_RESULT=FAIL"
  echo "GUARD_REASON=no_DATABASE_URL_and_no_env"
  echo "HINT=Run deploy/api/m1-db-source-discover.sh then restore .env only after DATABASE_SOURCE_CONFIRMED=YES"
  echo "EMPTY_SQLITE_FALLBACK_BLOCKED=YES"
  exit 1
fi

case "${DB_URL}" in
  postgres*://*|postgresql*://*)
    echo "GUARD_RESULT=PASS"
    echo "GUARD_DB_KIND=postgres"
    echo "DATABASE_URL_REDACTED=$(redact_url "${DB_URL}")"
    exit 0
    ;;
  sqlite*://*)
    # Absolute or relative path after sqlite:///
    path_part="${DB_URL#sqlite:///}"
    if [[ "${path_part}" == /* ]]; then
      sqlite_path="${path_part}"
    else
      sqlite_path="${BACKEND_DIR}/${path_part}"
    fi
    if [[ ! -f "${sqlite_path}" ]]; then
      echo "GUARD_RESULT=FAIL"
      echo "GUARD_REASON=sqlite_path_missing_refusing_create"
      echo "SQLITE_PATH_REDACTED=${sqlite_path}"
      exit 1
    fi
    # Non-empty file required (empty create would be disaster)
    sz="$(wc -c < "${sqlite_path}" 2>/dev/null | tr -d ' ' || echo 0)"
    if [[ "${sz}" -lt 1024 ]]; then
      echo "GUARD_RESULT=FAIL"
      echo "GUARD_REASON=sqlite_file_too_small_suspect_empty"
      exit 1
    fi
    echo "GUARD_RESULT=PASS"
    echo "GUARD_DB_KIND=sqlite_existing"
    echo "SQLITE_BYTES=${sz}"
    exit 0
    ;;
  *)
    echo "GUARD_RESULT=FAIL"
    echo "GUARD_REASON=unsupported_DATABASE_URL_scheme"
    echo "DATABASE_URL_REDACTED=$(redact_url "${DB_URL}")"
    exit 1
    ;;
esac
