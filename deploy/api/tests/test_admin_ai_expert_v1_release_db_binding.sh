#!/usr/bin/env bash
# Static regression: Admin AI Expert V1 production release script MUST bind
# huaqiao-postgres / 127.0.0.1:5433/huaqiao and must NOT use bare psql,
# localhost:5432, or hardcoded role=postgres fallback.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCR="${ROOT}/deploy/api/m1-admin-ai-expert-v1-production-release.sh"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

[[ -f "$SCR" ]] || { echo "missing $SCR"; exit 1; }

non="$(mktemp)"
# Strip full-line comments only (keep inline code)
grep -vE '^[[:space:]]*#' "$SCR" >"$non" || true

# --- Hard fails: unbound / wrong DB bindings ---
# Every psql invocation must share a physical line with `docker exec`.
psql_bad=0
while IFS= read -r line; do
  if echo "$line" | grep -qE '(^|[[:space:]])psql([[:space:]]|$)'; then
    if ! echo "$line" | grep -q 'docker exec'; then
      echo "unbound psql: $line"
      psql_bad=1
    fi
  fi
done < "$non"
if [[ "$psql_bad" -eq 0 ]]; then
  ok "no bare host psql (all psql lines include docker exec)"
else
  ko "bare host psql (must be docker exec only)"
fi

# Hardcoded -U postgres (role assumption) — allowed only if comparing/documenting block
if grep -nE '\-U[[:space:]]+postgres\b' "$non"; then
  ko "hardcoded -U postgres role assumption"
else
  ok "no hardcoded -U postgres"
fi

if grep -nE 'POSTGRES_USER:-postgres|_PG_USER:-postgres|PG_USER:-postgres' "$non"; then
  ko "postgres role fallback via \${VAR:-postgres}"
else
  ok "no postgres role default fallback"
fi

# Refuse production binding to 5432 (comments already stripped for full-line #)
if grep -nE '127\.0\.0\.1:5432|localhost:5432|:5432/huaqiao' "$non" \
  | grep -vE 'abort|refuse|BLOCKED|5432_BLOCKED|grep -qE|:5432/' ; then
  # Allow lines that only abort/refuse/detect 5432
  hits="$(grep -nE '127\.0\.0\.1:5432|localhost:5432' "$non" || true)"
  bad_hits="$(echo "$hits" | grep -viE 'abort|refuse|BLOCKED|5432_BLOCKED|grep|:5432/' || true)"
  if [[ -n "${bad_hits}" ]]; then
    echo "${bad_hits}"
    ko "production script binds or targets localhost:5432"
  else
    ok "no production target on :5432"
  fi
else
  ok "no production target on :5432"
fi

# Inside-container psql/pg_dump may use -h localhost -p 5432 (container local) — that is OK
# Host-side DATABASE_URL must require 5433
grep -qE '5433' "$SCR" && ok "requires port 5433" || ko "missing 5433 binding"

grep -q 'huaqiao-postgres' "$SCR" && ok "scoped to huaqiao-postgres" || ko "missing huaqiao-postgres"
grep -q 'POSTGRES_USER=' "$SCR" && ok "reads container POSTGRES_USER" || ko "does not read POSTGRES_USER"
grep -q 'load_container_pg_creds\|POSTGRES_USER=\*' "$SCR" && ok "container cred loader present" || ko "cred loader missing"

# Must redact DATABASE_URL
grep -qE 'DATABASE_URL_REDACTED|redact_url' "$SCR" && ok "DATABASE_URL redaction present" || ko "no URL redaction"

# Fingerprint + backup gates
grep -q '006_student_profile_slots' "$SCR" && ok "expects revision 006" || ko "missing 006 expect"
grep -q '007_admin_ai_expert_v1' "$SCR" && ok "expects revision 007" || ko "missing 007 expect"
grep -q 'EXPECTED_UNI=125' "$SCR" && ok "universities=125 guard" || ko "missing uni guard"
grep -q 'EXPECTED_TL=900' "$SCR" && ok "schedules=900 guard" || ko "missing timeline guard"
grep -q 'EXPECTED_USERS=2' "$SCR" && ok "users=2 guard" || ko "missing users guard"
grep -q 'DATABASE_FINGERPRINT_GUARD' "$SCR" && ok "fingerprint guard label" || ko "missing fingerprint guard"
grep -q 'pg_dump' "$SCR" && ok "pg_dump present" || ko "pg_dump missing"
grep -q 'pg_restore -l' "$SCR" && ok "pg_restore -l verify" || ko "pg_restore -l missing"
grep -q 'BACKUP_VERIFIED' "$SCR" && ok "backup verified gate" || ko "backup gate missing"
grep -q 'MIGRATION_ALLOWED_ONLY_AFTER_BACKUP\|BACKUP_BEFORE_MIGRATION' "$SCR" \
  && ok "backup-before-migrate gate" || ko "backup-before-migrate missing"
grep -q 'alembic upgrade head' "$SCR" && ok "alembic upgrade present" || ko "alembic upgrade missing"
grep -q 'DATA_INTEGRITY' "$SCR" && ok "data integrity gate" || ko "integrity missing"

# Forbidden ops
if grep -nE 'seed_data\(|\.create_all\(|auto[[:space:]]*pg_restore|pg_restore[[:space:]]+[^-].*huaqiao' "$non" \
  | grep -viE 'pg_restore -l|abort|HINT|AUTO_PG_RESTORE=NO|Do NOT auto' ; then
  ko "forbidden seed/create_all/auto-restore"
else
  ok "no seed/create_all/auto-restore"
fi

if grep -nE 'sqlite:///|\bsaas_pro\.db\b' "$non" | grep -viE 'BLOCKED|abort|refuse|SQLITE'; then
  ko "sqlite fallback present"
else
  ok "sqlite fallback blocked"
fi

# Negative fixture: a deliberately bad snippet must be detected by the same rules
BAD="$(mktemp)"
cat >"$BAD" <<'EOF'
pg_sql() { psql -U postgres -d huaqiao -Atc "$1"; }
docker exec huaqiao-postgres pg_dump -U postgres -Fc huaqiao
DATABASE_URL=postgresql://huaqiao:x@127.0.0.1:5432/huaqiao
EOF
bad_score=0
while IFS= read -r line; do
  if echo "$line" | grep -qE '(^|[[:space:]])psql([[:space:]]|$)'; then
    if ! echo "$line" | grep -q 'docker exec'; then
      bad_score=$((bad_score + 1))
    fi
  fi
done < "$BAD"
grep -nE '\-U[[:space:]]+postgres\b' "$BAD" >/dev/null && bad_score=$((bad_score + 1))
grep -nE '127\.0\.0\.1:5432' "$BAD" >/dev/null && bad_score=$((bad_score + 1))
if [[ "$bad_score" -eq 3 ]]; then
  ok "regression detector catches bare psql + postgres role + :5432"
else
  ko "regression detector incomplete (score=${bad_score})"
fi
rm -f "$BAD" "$non"

echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
