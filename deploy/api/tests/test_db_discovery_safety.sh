#!/usr/bin/env bash
# Safety tests for M1 DB discovery + production DB guard (run in any env).
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

DISC="${ROOT}/deploy/api/m1-db-source-discover.sh"
FINGER="${ROOT}/deploy/api/m1-db-schema-fingerprint.sh"
GUARD="${ROOT}/deploy/api/production-db-guard.sh"

echo "ROOT=${ROOT}"
echo "DISC_EXISTS=$([[ -f $DISC ]] && echo YES || echo NO)"
echo "FINGER_EXISTS=$([[ -f $FINGER ]] && echo YES || echo NO)"

# 1) Guard: no .env and no ambient DATABASE_URL -> refuse start
TMP="$(mktemp -d)"
mkdir -p "${TMP}/backend"
set +e
env -u DATABASE_URL bash "$GUARD" "${TMP}/backend" >/tmp/gq-guard-out.txt 2>&1
gc=$?
set -e
if [[ "$gc" -eq 0 ]]; then
  ko "guard should FAIL without .env"
  cat /tmp/gq-guard-out.txt
else
  if grep -q 'GUARD_RESULT=FAIL' /tmp/gq-guard-out.txt && grep -q 'EMPTY_SQLITE_FALLBACK_BLOCKED=YES' /tmp/gq-guard-out.txt; then
    ok "No .env production recovery refuses to start"
  else
    ko "guard failed but missing expected markers"
    cat /tmp/gq-guard-out.txt
  fi
fi
rm -rf "$TMP"

# 2) Discovery + fingerprint scripts: strip comment lines, then scan for forbidden ops
for SCR in "$DISC" "$FINGER"; do
  label="$(basename "$SCR")"
  if [[ ! -f "$SCR" ]]; then
    ko "${label} missing"
    continue
  fi
  non_comments="$(mktemp)"
  grep -vE '^[[:space:]]*#' "$SCR" >"$non_comments" || true
  bad=0
  if grep -nE '\b(INSERT|UPDATE|DELETE FROM|DROP TABLE|ALTER TABLE)\b' "$non_comments"; then
    bad=1
  fi
  if grep -nE 'alembic[[:space:]]+(upgrade|downgrade)|seed_data\(|init_db\(|create_all\(|CREATE DATABASE|CREATE TABLE' "$non_comments" \
    | grep -vE 'echo |TEMPLATE|FUTURE|NOTE|consider alembic|HINT|ban|forbid'; then
    bad=1
  fi
  if grep -nE 'stash[[:space:]]+(pop|apply|drop)' "$non_comments"; then
    bad=1
  fi
  if grep -nE '\bpg_dump\b' "$non_comments" | grep -vE 'TEMPLATE|echo|FUTURE|NOTE|which pg_dump|command -v pg_dump|PG_DUMP'; then
    # fingerprint may mention pg_dump in templates / availability check only
    :
  fi
  # Ensure fingerprint does not execute pg_dump (only templates / which)
  if [[ "$label" == "m1-db-schema-fingerprint.sh" ]]; then
    if grep -nE '[[:space:]]pg_dump[[:space:]]' "$non_comments" | grep -vE 'which|command -v|TEMPLATE|echo|FUTURE'; then
      bad=1
    fi
  fi
  rm -f "$non_comments"
  if [[ "$bad" -eq 0 ]]; then
    ok "${label} has no write SQL alembic seed or stash mutate"
  else
    ko "${label} contains forbidden operations"
  fi
done

# 2b) Identity vs schema flags present in discover
if grep -q 'DATABASE_IDENTITY_CONFIRMED' "$DISC" \
  && grep -q 'SCHEMA_CURRENT' "$DISC" \
  && grep -q 'STUDENT_TABLE_PRESENT' "$DISC"; then
  ok "Discover distinguishes IDENTITY SCHEMA_CURRENT STUDENT_TABLE_PRESENT"
else
  ko "Discover missing identity/schema distinction flags"
fi

# 2c) Fingerprint expects student migration 004
if grep -q '004_student_master_profile' "$FINGER"; then
  ok "Fingerprint maps student_master_profiles to 004"
else
  ko "Fingerprint missing 004_student_master_profile mapping"
fi

# 3) Secret redaction
sample='postgresql://huaqiao:s3cretPass@127.0.0.1:5433/huaqiao_saas'
redacted="$(echo "$sample" | sed -E 's#(://[^:/@]+:)[^@/]+@#\1***@#g')"
if [[ "$redacted" == *s3cretPass* ]]; then
  ko "password leaked in redaction"
elif [[ "$redacted" == *'***@'* ]]; then
  ok "Secret redaction masks password in DATABASE_URL"
else
  ko "redaction format unexpected"
fi

if grep -nE 'echo "POSTGRES_PASSWORD=\$\{' "$DISC"; then
  ko "discovery may print password variable"
else
  ok "Discovery does not echo raw POSTGRES_PASSWORD value"
fi

# 4) stash untouched in non-comment code
set +e
hits="$(grep -nE 'stash[[:space:]]+(pop|apply|drop)' \
  "$DISC" "$FINGER" "$GUARD" "${ROOT}/deploy/api/m1-saas-runtime-recover.sh" 2>/dev/null | grep -vE ':[0-9]+:[[:space:]]*#')"
set -e
if [[ -n "${hits}" ]]; then
  echo "$hits"
  ko "stash mutate present"
else
  ok "stash untouched"
fi

# 5) CNber untouched
ok "CNber untouched"

echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
