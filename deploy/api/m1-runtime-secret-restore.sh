#!/usr/bin/env bash
# Safely restore UNIQUE discovered runtime secrets into SaaS backend/.env.
# Prerequisites: m1-runtime-secret-discover.sh found exactly one trusted
# candidate for JWT_SECRET_KEY, VAULT_FERNET_KEY, and ADMIN_TOKEN.
#
# NEVER invents secrets. NEVER prints secret values.
# NEVER overwrites: DATABASE_URL GUOQIAO_SKIP_SEED PUBLIC_BASE_URL
#                   FRONTEND_BASE_URL CORS_ORIGINS
# NEVER runs alembic / seed / pg_restore / starts backend.
# NEVER commits .env.
#
# Usage (M1, after discover READY_FOR_SECRET_RESTORE=YES):
#   bash deploy/api/m1-runtime-secret-restore.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ENV_FILE="${BACKEND}/.env"
STATE_DIR="${HOME}/.guoqiao/saas"
PLAN_FILE="${STATE_DIR}/secret-restore.plan"
VALUES_FILE="${STATE_DIR}/secret-restore.values"

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

echo "============================================================"
echo "GUOQIAO M1 RUNTIME SECRET RESTORE"
echo "SECRET_OUTPUT_REDACTED=YES"
echo "DATABASE_CHANGED=NO"
echo "ENV_FILE=${ENV_FILE}"
echo "============================================================"

if [[ ! -f "${PLAN_FILE}" ]]; then
  echo "RESTORE_RESULT=FAIL"
  echo "REASON=missing_plan_run_discover_first"
  echo "SECRET_RECOVERY_COMPLETE=NO"
  echo "USER_ACTION_REQUIRED=YES"
  exit 1
fi

# Load plan flags (sources/fingerprints/unique) — no secret values in plan
JWT_UNIQUE=""; VAULT_UNIQUE=""; ADMIN_UNIQUE=""
JWT_SOURCE=""; VAULT_SOURCE=""; ADMIN_SOURCE=""
JWT_FINGERPRINT=""; VAULT_FINGERPRINT=""; ADMIN_FINGERPRINT=""
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  case "$line" in
    JWT_UNIQUE=*) JWT_UNIQUE="${line#JWT_UNIQUE=}" ;;
    VAULT_UNIQUE=*) VAULT_UNIQUE="${line#VAULT_UNIQUE=}" ;;
    ADMIN_UNIQUE=*) ADMIN_UNIQUE="${line#ADMIN_UNIQUE=}" ;;
    JWT_SOURCE=*) JWT_SOURCE="${line#JWT_SOURCE=}" ;;
    VAULT_SOURCE=*) VAULT_SOURCE="${line#VAULT_SOURCE=}" ;;
    ADMIN_SOURCE=*) ADMIN_SOURCE="${line#ADMIN_SOURCE=}" ;;
    JWT_FINGERPRINT=*) JWT_FINGERPRINT="${line#JWT_FINGERPRINT=}" ;;
    VAULT_FINGERPRINT=*) VAULT_FINGERPRINT="${line#VAULT_FINGERPRINT=}" ;;
    ADMIN_FINGERPRINT=*) ADMIN_FINGERPRINT="${line#ADMIN_FINGERPRINT=}" ;;
    VALUES_FILE=*) VALUES_FILE="${line#VALUES_FILE=}" ;;
  esac
done <"${PLAN_FILE}"

if [[ ! -f "${VALUES_FILE}" ]]; then
  echo "RESTORE_RESULT=FAIL"
  echo "REASON=missing_values_file"
  echo "SECRET_RECOVERY_COMPLETE=NO"
  echo "USER_ACTION_REQUIRED=YES"
  exit 1
fi

if [[ "${JWT_UNIQUE}" != "YES" || "${VAULT_UNIQUE}" != "YES" || "${ADMIN_UNIQUE}" != "YES" ]]; then
  echo "RESTORE_RESULT=FAIL"
  echo "REASON=not_all_unique_refuse_auto_pick"
  echo "JWT_UNIQUE=${JWT_UNIQUE:-NO}"
  echo "VAULT_UNIQUE=${VAULT_UNIQUE:-NO}"
  echo "ADMIN_UNIQUE=${ADMIN_UNIQUE:-NO}"
  echo "SECRET_RECOVERY_COMPLETE=NO"
  echo "USER_ACTION_REQUIRED=YES"
  echo "HINT=Re-run discover or manually confirm candidates by fingerprint; do not invent secrets."
  exit 1
fi

JWT_VAL=""; VAULT_VAL=""; ADMIN_VAL=""
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  key="${line%%=*}"
  val="${line#*=}"
  case "$key" in
    JWT_SECRET_KEY) JWT_VAL="$val" ;;
    VAULT_FERNET_KEY) VAULT_VAL="$val" ;;
    ADMIN_TOKEN) ADMIN_VAL="$val" ;;
  esac
done <"${VALUES_FILE}"

if [[ -z "$JWT_VAL" || -z "$VAULT_VAL" || -z "$ADMIN_VAL" ]]; then
  echo "RESTORE_RESULT=FAIL"
  echo "REASON=values_file_incomplete"
  echo "SECRET_RECOVERY_COMPLETE=NO"
  echo "USER_ACTION_REQUIRED=YES"
  exit 1
fi

fp_jwt="$(fingerprint "$JWT_VAL")"
fp_vault="$(fingerprint "$VAULT_VAL")"
fp_admin="$(fingerprint "$ADMIN_VAL")"
if [[ -n "${JWT_FINGERPRINT}" && "$fp_jwt" != "$JWT_FINGERPRINT" ]]; then
  echo "RESTORE_RESULT=FAIL"
  echo "REASON=jwt_fingerprint_mismatch"
  exit 1
fi
if [[ -n "${VAULT_FINGERPRINT}" && "$fp_vault" != "$VAULT_FINGERPRINT" ]]; then
  echo "RESTORE_RESULT=FAIL"
  echo "REASON=vault_fingerprint_mismatch"
  exit 1
fi
if [[ -n "${ADMIN_FINGERPRINT}" && "$fp_admin" != "$ADMIN_FINGERPRINT" ]]; then
  echo "RESTORE_RESULT=FAIL"
  echo "REASON=admin_fingerprint_mismatch"
  exit 1
fi

GUOQIAO_CAND="$VAULT_VAL" python3 - <<'PY'
import os, sys, base64
k = os.environ["GUOQIAO_CAND"].encode("utf-8")
try:
    from cryptography.fernet import Fernet
    Fernet(k)
except ImportError:
    raw = base64.urlsafe_b64decode(k)
    if len(raw) != 32:
        raise SystemExit(1)
except Exception:
    raise SystemExit(1)
PY

mkdir -p "${BACKEND}"
if [[ ! -f "${ENV_FILE}" ]]; then
  touch "${ENV_FILE}"
fi
chmod 600 "${ENV_FILE}"

TMP="$(mktemp)"
chmod 600 "$TMP"
BAK="${ENV_FILE}.bak.$(date +%Y%m%d%H%M%S)"
cp "${ENV_FILE}" "${BAK}"
chmod 600 "${BAK}"

STATUS_OUT="$(
  GUOQIAO_ENV_FILE="${ENV_FILE}" \
  GUOQIAO_TMP="$TMP" \
  GUOQIAO_JWT="$JWT_VAL" \
  GUOQIAO_VAULT="$VAULT_VAL" \
  GUOQIAO_ADMIN="$ADMIN_VAL" \
  python3 - <<'PY'
import os
env_path = os.environ["GUOQIAO_ENV_FILE"]
tmp_path = os.environ["GUOQIAO_TMP"]
wanted = {
    "JWT_SECRET_KEY": os.environ["GUOQIAO_JWT"],
    "VAULT_FERNET_KEY": os.environ["GUOQIAO_VAULT"],
    "ADMIN_TOKEN": os.environ["GUOQIAO_ADMIN"],
}
protected = {
    "DATABASE_URL",
    "GUOQIAO_SKIP_SEED",
    "PUBLIC_BASE_URL",
    "FRONTEND_BASE_URL",
    "CORS_ORIGINS",
}
order = []
kv = {}
comments_before = {}
raw_lines = open(env_path, "r", encoding="utf-8", errors="replace").read().splitlines()
pending_comments = []
for line in raw_lines:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in line:
        pending_comments.append(line)
        continue
    key, _, val = line.partition("=")
    key = key.strip()
    if key not in kv:
        order.append(key)
        comments_before[key] = pending_comments
        pending_comments = []
        kv[key] = val
trailing = pending_comments
filled = []
skipped_present = []
for k, v in wanted.items():
    if k in kv and str(kv[k]).strip() != "":
        skipped_present.append(k)
        continue
    if k not in kv:
        order.append(k)
        comments_before[k] = []
    kv[k] = v
    filled.append(k)

with open(tmp_path, "w", encoding="utf-8") as out:
    for k in order:
        for c in comments_before.get(k, []):
            out.write(c + "\n")
        out.write(f"{k}={kv[k]}\n")
    for c in trailing:
        out.write(c + "\n")

print("FILLED=" + ",".join(filled))
print("SKIPPED_ALREADY_SET=" + ",".join(skipped_present))
print("PROTECTED_PRESERVED=" + ",".join(sorted(k for k in protected if k in kv)))
PY
)"

mv "$TMP" "${ENV_FILE}"
chmod 600 "${ENV_FILE}"

# Verify protected keys unchanged vs backup
python3 - <<PY
import pathlib, sys
bak = pathlib.Path("${BAK}").read_text(encoding="utf-8", errors="replace")
env = pathlib.Path("${ENV_FILE}").read_text(encoding="utf-8", errors="replace")

def parse(text):
    out = {}
    for line in text.splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v
    return out

b, e = parse(bak), parse(env)
protected = ["DATABASE_URL", "GUOQIAO_SKIP_SEED", "PUBLIC_BASE_URL", "FRONTEND_BASE_URL", "CORS_ORIGINS"]
for k in protected:
    if k in b and b[k] != e.get(k):
        print("VERIFY=FAIL protected_changed=" + k)
        sys.exit(1)
for k in ("JWT_SECRET_KEY", "VAULT_FERNET_KEY", "ADMIN_TOKEN"):
    if k not in e or not str(e[k]).strip():
        print("VERIFY=FAIL missing=" + k)
        sys.exit(1)
print("VERIFY=OK")
PY

unset JWT_VAL VAULT_VAL ADMIN_VAL 2>/dev/null || true

echo "$STATUS_OUT"
echo "JWT_SECRET_SOURCE=${JWT_SOURCE}"
echo "JWT_SECRET_FINGERPRINT=${fp_jwt}"
echo "VAULT_SECRET_SOURCE=${VAULT_SOURCE}"
echo "VAULT_SECRET_FINGERPRINT=${fp_vault}"
echo "ADMIN_TOKEN_SOURCE=${ADMIN_SOURCE}"
echo "ADMIN_TOKEN_FINGERPRINT=${fp_admin}"
echo "ENV_BACKUP=${BAK}"
echo "ENV_CHMOD=600"
echo "ENV_COMMITTED=NO"
echo "DATABASE_CHANGED=NO"
echo "MIGRATION_RUN=NO"
echo "RESTORE_RESULT=OK"
echo "SECRET_RECOVERY_COMPLETE=YES"
echo "USER_ACTION_REQUIRED=NO"
echo "NEXT_ACTION=start_saas_backend_via_LaunchAgent — do NOT re-run DB upgrade"
echo "============================================================"
exit 0
