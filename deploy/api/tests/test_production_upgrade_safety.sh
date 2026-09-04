#!/usr/bin/env bash
# Static safety tests for m1-production-db-upgrade-recover.sh
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCR="${ROOT}/deploy/api/m1-production-db-upgrade-recover.sh"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

[[ -f "$SCR" ]] || { echo "missing script"; exit 1; }

non="$(mktemp)"
grep -vE '^[[:space:]]*#' "$SCR" >"$non" || true

bad=0

# Forbidden executable ops (ignore lines that only document/forbid them)
scan_forbidden() {
  local pat="$1"
  local hits
  hits="$(grep -nE "$pat" "$non" || true)"
  if [[ -z "$hits" ]]; then
    return 0
  fi
  # Drop documentation / guard strings
  hits="$(echo "$hits" | grep -viE 'abort|forbid|forbidden|Never|never|GUARD|assert_safe|HINT|echo \"CNBER|SQLITE_FALLBACK=BLOCKED' || true)"
  if [[ -n "$hits" ]]; then
    echo "$hits"
    return 1
  fi
  return 0
}

if ! scan_forbidden 'seed_data\(|create_all\(|stash[[:space:]]+(pop|apply|drop)|reset[[:space:]]+--hard'; then
  bad=1
fi
if ! scan_forbidden 'docker[[:space:]]+compose[[:space:]]+down|docker-compose[[:space:]]+down|docker[[:space:]]+system[[:space:]]+prune'; then
  bad=1
fi
if ! scan_forbidden 'docker[[:space:]]+stop[[:space:]]+\$\(|\bkillall\b|\bpkill[[:space:]]+-9'; then
  bad=1
fi
if ! scan_forbidden 'echo.*"\$\{_PG_PASS\}"|echo.*POSTGRES_PASSWORD=\$\{_PG_PASS\}'; then
  bad=1
fi
# Must mention sqlite fallback is blocked, must not create saas_pro.db
if grep -q 'saas_pro\.db' "$non" && ! grep -qiE 'BLOCKED|abort|forbid' "$non"; then
  echo "unexpected saas_pro.db use"
  bad=1
fi

if [[ "$bad" -eq 0 ]]; then
  ok "no seed/create_all/stash/broad-docker/secret-echo"
else
  ko "forbidden patterns present"
fi

grep -q 'pg_dump' "$SCR" && ok "pg_dump present" || ko "pg_dump missing"
grep -q 'pg_restore -l' "$SCR" && ok "pg_restore -l verify present" || ko "pg_restore -l missing"
grep -q 'alembic upgrade head' "$SCR" && ok "alembic upgrade head present" || ko "alembic upgrade missing"
grep -q 'GUOQIAO_SKIP_SEED=1' "$SCR" && ok "skip seed enforced" || ko "skip seed missing"
grep -q 'huaqiao-postgres' "$SCR" && ok "container scoped to huaqiao-postgres" || ko "container scope missing"
grep -q 'quote(' "$SCR" && ok "password URL encoding present" || ko "URL encoding missing"
grep -q 'BACKUP_VERIFIED' "$SCR" && ok "backup verify gate present" || ko "backup gate missing"
grep -q 'DATA_INTEGRITY' "$SCR" && ok "data integrity gate present" || ko "integrity gate missing"
grep -q 'SQLITE_FALLBACK=BLOCKED' "$SCR" && ok "sqlite fallback blocked banner" || ko "sqlite blocked banner missing"

if grep -q 'GUOQIAO_SKIP_SEED' "${ROOT}/huaqiao-saas-pro/backend/app/main.py"; then
  ok "main.py honors GUOQIAO_SKIP_SEED"
else
  ko "main.py missing GUOQIAO_SKIP_SEED"
fi

rm -f "$non"
echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
