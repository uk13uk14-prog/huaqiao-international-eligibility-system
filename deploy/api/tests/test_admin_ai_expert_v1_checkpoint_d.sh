#!/usr/bin/env bash
# Regression: CHECKPOINT D must not silently exit; must use .venv alembic binding.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCR="${ROOT}/deploy/api/m1-admin-ai-expert-v1-production-release.sh"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

[[ -f "$SCR" ]] || { echo "missing $SCR"; exit 1; }
non="$(mktemp)"
grep -vE '^[[:space:]]*#' "$SCR" >"$non" || true

# Forbidden: system python3 -m alembic (root cause of silent failure on M1)
if grep -nE 'python3[[:space:]]+-m[[:space:]]+alembic' "$non"; then
  ko "uses system python3 -m alembic"
else
  ok "no system python3 -m alembic"
fi

# Forbidden: swallowing alembic CLI stderr (the silent-exit pattern)
if grep -nE '(python3[[:space:]]+-m[[:space:]]+alembic|alembic[[:space:]]+(current|heads|upgrade))[^\n]*2>/dev/null' "$non"; then
  ko "alembic CLI stderr swallowed with 2>/dev/null"
else
  ok "alembic CLI stderr not swallowed"
fi

grep -q '\.venv/bin/python' "$SCR" && ok "uses backend .venv python" || ko "missing .venv python"
grep -q 'alembic_bound' "$SCR" && ok "alembic_bound helper present" || ko "missing alembic_bound"
grep -q 'replace("%", "%%")' "$SCR" && ok "ConfigParser % escaping" || ko "missing % escaping"
grep -q 'PSYCOPG_IMPORT' "$SCR" && ok "psycopg import check" || ko "missing psycopg check"
grep -q 'CHECKPOINT_D_DIAGNOSTIC' "$SCR" && ok "diagnostic label" || ko "missing diagnostic"
grep -q 'DIRECT_DB_REVISION' "$SCR" && ok "DIRECT_DB_REVISION" || ko "missing DIRECT_DB_REVISION"
grep -q 'ALEMBIC_CURRENT' "$SCR" && ok "ALEMBIC_CURRENT" || ko "missing ALEMBIC_CURRENT"
grep -q 'ALEMBIC_HEADS' "$SCR" && ok "ALEMBIC_HEADS" || ko "missing ALEMBIC_HEADS"
grep -q 'ALEMBIC_DATABASE_TARGET' "$SCR" && ok "ALEMBIC_DATABASE_TARGET" || ko "missing target label"
grep -q 'MIGRATION=FAIL' "$SCR" && ok "MIGRATION=FAIL visibility" || ko "missing MIGRATION=FAIL"
grep -q 'MIGRATION_EXIT_CODE' "$SCR" && ok "MIGRATION_EXIT_CODE" || ko "missing exit code field"
grep -q 'MIGRATION_STDERR_REDACTED' "$SCR" && ok "MIGRATION_STDERR_REDACTED" || ko "missing stderr field"
grep -q 'DB_REVISION_AFTER_FAILED_ATTEMPT' "$SCR" && ok "DB_REVISION_AFTER_FAILED_ATTEMPT" || ko "missing after-fail rev"
grep -q 'ROLLBACK_REQUIRED' "$SCR" && ok "ROLLBACK_REQUIRED" || ko "missing ROLLBACK_REQUIRED"
grep -q -- '--checkpoint-d-diagnostic-only' "$SCR" && ok "diagnostic-only flag" || ko "missing diagnostic-only flag"
grep -q 'POSTGRES_TRANSACTIONAL_DDL' "$SCR" && ok "transactional DDL note" || ko "missing transactional DDL"
grep -q 'MIGRATION_PARTIAL_OR_INCONSISTENT' "$SCR" && ok "partial migration detection" || ko "missing partial detect"
grep -q 'report_migration_failure' "$SCR" && ok "report_migration_failure helper" || ko "missing failure reporter"

# Must still refuse :5432 / postgres role / bare psql (from prior binding fix)
if grep -nE '\-U[[:space:]]+postgres\b' "$non"; then
  ko "hardcoded -U postgres returned"
else
  ok "still no -U postgres"
fi

# Negative fixture: old silent pattern must be detectable
BAD="$(mktemp)"
cat >"$BAD" <<'EOF'
BEFORE="$(python3 -m alembic current 2>/dev/null | tail -1 | awk '{print $1}')"
GUOQIAO_SKIP_SEED=1 python3 -m alembic upgrade head
EOF
bad=0
grep -qE 'python3[[:space:]]+-m[[:space:]]+alembic' "$BAD" && bad=$((bad + 1))
grep -qE 'alembic.*2>/dev/null' "$BAD" && bad=$((bad + 1))
if [[ "$bad" -eq 2 ]]; then
  ok "detector catches old silent alembic pattern"
else
  ko "detector incomplete for silent alembic (bad=${bad})"
fi

bash -n "$SCR" && ok "bash -n syntax" || ko "bash -n failed"

rm -f "$BAD" "$non"
echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
