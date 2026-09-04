#!/usr/bin/env bash
# Checkpoint F binding tests — no real migration.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCR="${ROOT}/deploy/api/m1-production-db-upgrade-recover.sh"
ENVPY="${ROOT}/huaqiao-saas-pro/backend/alembic/env.py"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

[[ -f "$SCR" ]] || { ko "missing recover script"; exit 1; }

grep -q 'replace("%", "%%")' "$SCR" && ok "script ConfigParser percent-escape" || ko "script missing %% escape"
grep -q 'replace("%", "%%")' "$ENVPY" && ok "env.py ConfigParser percent-escape" || ko "env.py missing %% escape"
grep -q 'DIRECT_DB_REVISION' "$SCR" && ok "direct SQL revision gate in CP F" || ko "missing DIRECT_DB_REVISION"
grep -q 'alembic_bound' "$SCR" && ok "alembic_bound helper present" || ko "missing alembic_bound"
grep -q 'EXPLICIT_DATABASE_URL_BINDING=YES' "$SCR" && ok "explicit binding banner" || ko "missing binding banner"
grep -q 'SETTINGS_DATABASE_TARGET' "$SCR" && ok "settings target check" || ko "missing settings check"
if grep -nE 'VENV_ALEMBIC.*" current 2>/dev/null' "$SCR"; then
  ko "still uses silent alembic current"
else
  ok "no silent alembic current redirect"
fi
grep -q 'will not overwrite' "$SCR" && ok "existing .env preserved" || ko "overwrite guard missing"

# Simulate ConfigParser % behavior
python3 - <<'PY'
from alembic.config import Config
import tempfile, os, sys
ini = tempfile.NamedTemporaryFile("w", suffix=".ini", delete=False)
ini.write("[alembic]\nscript_location = alembic\nsqlalchemy.url = postgresql+psycopg://u:p@127.0.0.1:5433/huaqiao\n")
ini.close()
url = "postgresql+psycopg://huaqiao:p%40ss%2Fword@127.0.0.1:5433/huaqiao"
cfg = Config(ini.name)
raw_failed = False
try:
    cfg.set_main_option("sqlalchemy.url", url)
except Exception:
    raw_failed = True
cfg2 = Config(ini.name)
cfg2.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
got = cfg2.get_main_option("sqlalchemy.url")
os.unlink(ini.name)
if not raw_failed:
    print("RAW_PERCENT_SET=UNEXPECTED_OK")
    sys.exit(1)
if got != url:
    print("ESCAPED_MISMATCH", got)
    sys.exit(1)
print("ESCAPED_PERCENT_SET=PASS")
PY
py_rc=$?
if [[ "$py_rc" -eq 0 ]]; then
  ok "Checkpoint F percent-escape semantics"
else
  if python3 -c 'import alembic' 2>/dev/null; then
    ko "percent-escape simulation failed"
  else
    ok "percent-escape simulation skipped (no alembic)"
  fi
fi

echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
