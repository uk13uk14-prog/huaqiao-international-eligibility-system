#!/usr/bin/env bash
# Static safety tests for M1 runtime secret discovery + restore (no real secrets).
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

DISC="${ROOT}/deploy/api/m1-runtime-secret-discover.sh"
REST="${ROOT}/deploy/api/m1-runtime-secret-restore.sh"

echo "ROOT=${ROOT}"

for SCR in "$DISC" "$REST"; do
  label="$(basename "$SCR")"
  if [[ ! -f "$SCR" ]]; then
    ko "${label} missing"
    continue
  fi
  if ! bash -n "$SCR"; then
    ko "${label} bash -n failed"
    continue
  fi
  ok "${label} bash -n"

  non_comments="$(mktemp)"
  grep -vE '^[[:space:]]*#' "$SCR" >"$non_comments" || true
  bad=0
  if grep -nE '\b(INSERT|UPDATE|DELETE FROM|DROP TABLE|ALTER TABLE)\b' "$non_comments"; then
    bad=1
  fi
  if grep -nE 'alembic[[:space:]]+(upgrade|downgrade)|seed_data\(|init_db\(|create_all\(|pg_restore|pg_dump' "$non_comments" \
    | grep -vE 'echo |NOTE|HINT|ban|forbid|NEVER|do NOT'; then
    bad=1
  fi
  if grep -nE 'stash[[:space:]]+(pop|apply|drop)' "$non_comments"; then
    bad=1
  fi
  # Must not echo secret variable expansions to stdout in obvious ways
  if grep -nE 'echo[[:space:]]+"\$\{?(JWT_VAL|VAULT_VAL|ADMIN_VAL|GUOQIAO_JWT|GUOQIAO_VAULT|GUOQIAO_ADMIN)' "$non_comments"; then
    bad=1
  fi
  if grep -nE 'echo[[:space:]]+.*JWT_SECRET_KEY=\$' "$non_comments"; then
    bad=1
  fi
  rm -f "$non_comments"
  if [[ "$bad" -eq 0 ]]; then
    ok "${label} no DB mutate / stash mutate / secret echo"
  else
    ko "${label} forbidden pattern"
  fi
done

# Discover must document redaction contract
if grep -q 'SECRET_OUTPUT_REDACTED=YES' "$DISC" \
  && grep -q 'JWT_SECRET_KEY_FOUND' "$DISC" \
  && grep -q 'JWT_SECRET_FINGERPRINT' "$DISC" \
  && grep -q 'VAULT_SECRET_SOURCE' "$DISC" \
  && grep -q 'ADMIN_TOKEN_SOURCE' "$DISC"; then
  ok "Discover reports FOUND/SOURCE/FINGERPRINT contract"
else
  ko "Discover missing report contract"
fi

# Discover must refuse inventing / require unique
if grep -q 'READY_FOR_SECRET_RESTORE' "$DISC" \
  && grep -q 'USER_ACTION_REQUIRED=YES' "$DISC" \
  && grep -q 'IMPACT_VAULT' "$DISC"; then
  ok "Discover has not-found impact messaging"
else
  ko "Discover missing impact messaging"
fi

# Restore must protect existing env keys
for k in DATABASE_URL GUOQIAO_SKIP_SEED PUBLIC_BASE_URL FRONTEND_BASE_URL CORS_ORIGINS; do
  if grep -q "$k" "$REST"; then
    :
  else
    ko "Restore missing protected key $k"
    k=FAIL
  fi
done
if grep -q 'PROTECTED' "$REST" || grep -q 'protected' "$REST"; then
  ok "Restore protects DATABASE_URL / seed / URLs / CORS"
else
  ko "Restore missing protected-key logic"
fi

# Restore refuses non-unique
if grep -q 'not_all_unique_refuse_auto_pick' "$REST"; then
  ok "Restore refuses non-unique candidates"
else
  ko "Restore missing unique gate"
fi

# Restore must not invent Fernet/JWT
if grep -nE 'Fernet\.generate_key|secrets\.token|openssl rand|uuidgen' "$REST" \
  | grep -vE 'echo |NOTE|NEVER'; then
  ko "Restore may invent secrets"
else
  ok "Restore does not invent secrets"
fi

# Functional: restore with fake unique plan fills only missing secrets
TMPHOME="$(mktemp -d)"
export HOME="$TMPHOME"
mkdir -p "${HOME}/.guoqiao/saas" "${ROOT}/huaqiao-saas-pro/backend"
PLAN="${HOME}/.guoqiao/saas/secret-restore.plan"
VALS="${HOME}/.guoqiao/saas/secret-restore.values"
ENVF="${ROOT}/huaqiao-saas-pro/backend/.env"
# Use a throwaway env path under TMP to avoid touching real .env
BACKEND_TMP="$(mktemp -d)"
mkdir -p "${BACKEND_TMP}/huaqiao-saas-pro/backend"
# Patch via env by running restore from a copy? Simpler: unit-test merge logic inline
printf '%s\n' \
  'DATABASE_URL=postgresql+psycopg://huaqiao:***@127.0.0.1:5433/huaqiao' \
  'GUOQIAO_SKIP_SEED=1' \
  'PUBLIC_BASE_URL=https://api.guoqiaoplan.com' \
  'FRONTEND_BASE_URL=https://app.guoqiaoplan.com' \
  'CORS_ORIGINS=https://app.guoqiaoplan.com' \
  >"${BACKEND_TMP}/huaqiao-saas-pro/backend/.env"
chmod 600 "${BACKEND_TMP}/huaqiao-saas-pro/backend/.env"

# Generate valid-looking Fernet key (32 bytes urlsafe b64)
FERNET="$(python3 -c 'import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())')"
JWT="test-jwt-secret-not-for-prod-abc"
ADMIN="test-admin-token-xyz"
fp_jwt="$(printf '%s' "$JWT" | sha256sum | awk '{print substr($1,1,12)}')"
fp_vault="$(printf '%s' "$FERNET" | sha256sum | awk '{print substr($1,1,12)}')"
fp_admin="$(printf '%s' "$ADMIN" | sha256sum | awk '{print substr($1,1,12)}')"

cat >"$PLAN" <<EOF
JWT_UNIQUE=YES
VAULT_UNIQUE=YES
ADMIN_UNIQUE=YES
JWT_SOURCE=test:fixture
VAULT_SOURCE=test:fixture
ADMIN_SOURCE=test:fixture
JWT_FINGERPRINT=${fp_jwt}
VAULT_FINGERPRINT=${fp_vault}
ADMIN_FINGERPRINT=${fp_admin}
VALUES_FILE=${VALS}
EOF
chmod 600 "$PLAN"
printf 'JWT_SECRET_KEY=%s\nVAULT_FERNET_KEY=%s\nADMIN_TOKEN=%s\n' "$JWT" "$FERNET" "$ADMIN" >"$VALS"
chmod 600 "$VALS"

# Run restore against temp tree by overriding ROOT via symlink trick:
# Create a wrapper that sets ROOT — instead, sed-copy restore with ROOT injected.
REST_TMP="$(mktemp)"
sed "s|^ROOT=.*|ROOT=\"${BACKEND_TMP}\"|" "$REST" >"$REST_TMP"
chmod +x "$REST_TMP"
set +e
out="$(bash "$REST_TMP" 2>&1)"
rc=$?
set -e
echo "$out" | grep -E 'JWT_SECRET_KEY=|VAULT_FERNET_KEY=|ADMIN_TOKEN=' && ko "restore leaked secret values" || ok "restore stdout has no secret values"
if [[ "$rc" -eq 0 ]] && echo "$out" | grep -q 'RESTORE_RESULT=OK'; then
  ok "restore succeeded on fixture"
else
  ko "restore failed on fixture"
  echo "$out"
fi
ENV_OUT="${BACKEND_TMP}/huaqiao-saas-pro/backend/.env"
if grep -q '^DATABASE_URL=postgresql+psycopg://huaqiao:\*\*\*@127.0.0.1:5433/huaqiao$' "$ENV_OUT" \
  && grep -q '^GUOQIAO_SKIP_SEED=1$' "$ENV_OUT" \
  && grep -q '^PUBLIC_BASE_URL=https://api.guoqiaoplan.com$' "$ENV_OUT" \
  && grep -q '^JWT_SECRET_KEY=' "$ENV_OUT" \
  && grep -q '^VAULT_FERNET_KEY=' "$ENV_OUT" \
  && grep -q '^ADMIN_TOKEN=' "$ENV_OUT"; then
  ok "restore filled secrets and preserved protected keys"
else
  ko "restore .env merge incorrect"
  cat "$ENV_OUT"
fi

# Non-unique refuse
sed -i 's/JWT_UNIQUE=YES/JWT_UNIQUE=NO/' "$PLAN"
set +e
out2="$(bash "$REST_TMP" 2>&1)"
rc2=$?
set -e
if [[ "$rc2" -ne 0 ]] && echo "$out2" | grep -q 'not_all_unique_refuse_auto_pick'; then
  ok "restore refuses when not unique"
else
  ko "restore should refuse non-unique"
  echo "$out2"
fi

rm -rf "$TMPHOME" "$BACKEND_TMP" "$REST_TMP"
# Do not leave FERNET/JWT in shell history of this test process beyond this
unset FERNET JWT ADMIN

echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
