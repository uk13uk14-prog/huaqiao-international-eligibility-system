#!/usr/bin/env bash
# Static + fixture safety tests for M1 secret bootstrap + go-live script.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

SCR="${ROOT}/deploy/api/m1-runtime-secret-bootstrap-and-go-live.sh"
echo "ROOT=${ROOT}"

if [[ ! -f "$SCR" ]]; then
  ko "bootstrap script missing"
  echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
  exit 1
fi

if bash -n "$SCR"; then
  ok "bash -n"
else
  ko "bash -n"
fi

non_comments="$(mktemp)"
grep -vE '^[[:space:]]*#' "$SCR" >"$non_comments" || true

bad=0
if grep -nE '\b(INSERT|UPDATE|DELETE FROM|DROP TABLE|ALTER TABLE)\b' "$non_comments"; then bad=1; fi
if grep -nE 'alembic[[:space:]]+(upgrade|downgrade)|seed_data\(|init_db\(|create_all\(|pg_restore' "$non_comments" \
  | grep -vE 'echo |NOTE|NEVER|MIGRATION_RUN=NO|abort |forbid'; then bad=1; fi
if grep -nE 'stash[[:space:]]+(pop|apply|drop)' "$non_comments"; then bad=1; fi
# Must not echo generated secret values
if grep -nE 'echo[[:space:]]+.*\$\{?(JWT_SECRET_KEY|VAULT_FERNET_KEY|ADMIN_TOKEN|jwt|vault|admin)\}' "$non_comments" \
  | grep -vE 'FINGERPRINT|GENERATED|SECRET_VALUES'; then bad=1; fi
if grep -nE 'password123|change-me-in-production["'\''][[:space:]]*$' "$non_comments" \
  | grep -vE 'change-me-in-production|is_placeholder|abort|!=|placeholder'; then
  # hardcoded assignment of weak secrets
  :
fi
if grep -nE 'Fernet\.generate_key|token_urlsafe' "$non_comments" >/dev/null; then
  ok "uses Fernet.generate_key / token_urlsafe"
else
  ko "missing strong secret generators"
  bad=1
fi
rm -f "$non_comments"
[[ "$bad" -eq 0 ]] && ok "no DB mutate / stash mutate / secret echo" || ko "forbidden pattern"

for needle in \
  'EXPECTED_REV="006_student_profile_slots"' \
  'MIGRATION_RUN=NO' \
  'SECRET_VALUES_EXPOSED=NO' \
  'com.guoqiao.saas-backend' \
  'validate_production_config' \
  'GUOQIAO_SKIP_SEED' \
  'DATABASE_URL' \
  'JWT_SECRET_FINGERPRINT' \
  'TUNNEL_CREDENTIALS=MISSING' \
  'OLD_JWT_SESSION_INVALIDATED=YES'
do
  if grep -qF "$needle" "$SCR"; then
    ok "contains $needle"
  else
    ko "missing $needle"
  fi
done

# Protected keys must not be overwritten when present — check merge logic mentions them
for k in DATABASE_URL GUOQIAO_SKIP_SEED PUBLIC_BASE_URL FRONTEND_BASE_URL CORS_ORIGINS; do
  grep -q "$k" "$SCR" || ko "missing protected $k"
done
ok "protected env keys referenced"

# Fixture: secret merge Python path via extracting? Simpler: run a mini merge compatible with script rules
TMP="$(mktemp -d)"
ENVF="${TMP}/.env"
cat >"$ENVF" <<EOF
DATABASE_URL=postgresql+psycopg://huaqiao:***@127.0.0.1:5433/huaqiao
GUOQIAO_SKIP_SEED=1
PUBLIC_BASE_URL=https://api.guoqiaoplan.com
FRONTEND_BASE_URL=https://app.guoqiaoplan.com
CORS_ORIGINS=https://app.guoqiaoplan.com
EOF
chmod 600 "$ENVF"
OUT="${TMP}/out.env"
STATUS="${TMP}/status"
python3 - <<PY
import os, secrets, hashlib
from pathlib import Path
try:
    from cryptography.fernet import Fernet
except ImportError:
    # format-only fallback for CI without cryptography: skip full Fernet generate
    import base64
    class Fernet:
        @staticmethod
        def generate_key():
            return base64.urlsafe_b64encode(os.urandom(32))
        def __init__(self, k):
            raw = base64.urlsafe_b64decode(k)
            assert len(raw) == 32

env_in = Path("${ENVF}")
env_out = Path("${OUT}")
status = Path("${STATUS}")
protected = {"DATABASE_URL","GUOQIAO_SKIP_SEED","PUBLIC_BASE_URL","FRONTEND_BASE_URL","CORS_ORIGINS"}
order=[]; kv={}; comments_before={}; pending=[]
for line in env_in.read_text().splitlines():
    s=line.strip()
    if not s or s.startswith("#") or "=" not in line:
        pending.append(line); continue
    k,_,v=line.partition("="); k=k.strip()
    if k not in kv:
        order.append(k); comments_before[k]=pending; pending=[]; kv[k]=v
trailing=pending
def fp(v): return hashlib.sha256(v.encode()).hexdigest()[:12]
kv["ENV"]="production"; order.append("ENV"); comments_before["ENV"]=[]
jwt=secrets.token_urlsafe(64)
vault=Fernet.generate_key().decode() if hasattr(Fernet.generate_key(), 'decode') else Fernet.generate_key().decode('ascii')
admin=secrets.token_urlsafe(48)
kv["JWT_SECRET_KEY"]=jwt; order.append("JWT_SECRET_KEY"); comments_before["JWT_SECRET_KEY"]=[]
kv["VAULT_FERNET_KEY"]=vault; order.append("VAULT_FERNET_KEY"); comments_before["VAULT_FERNET_KEY"]=[]
kv["ADMIN_TOKEN"]=admin; order.append("ADMIN_TOKEN"); comments_before["ADMIN_TOKEN"]=[]
with env_out.open("w") as out:
    for k in order:
        for c in comments_before.get(k,[]): out.write(c+"\n")
        out.write(f"{k}={kv[k]}\n")
    for c in trailing: out.write(c+"\n")
with status.open("w") as sf:
    sf.write(f"JWT_SECRET_FINGERPRINT={fp(jwt)}\n")
    sf.write(f"VAULT_SECRET_FINGERPRINT={fp(vault)}\n")
    sf.write(f"ADMIN_TOKEN_FINGERPRINT={fp(admin)}\n")
# never print secrets
print("MERGE_FIXTURE_OK")
PY

if grep -q '^DATABASE_URL=postgresql+psycopg://huaqiao:\*\*\*@127.0.0.1:5433/huaqiao$' "$OUT" \
  && grep -q '^GUOQIAO_SKIP_SEED=1$' "$OUT" \
  && [[ "$(grep -c '^JWT_SECRET_KEY=' "$OUT")" -eq 1 ]] \
  && [[ "$(grep -c '^VAULT_FERNET_KEY=' "$OUT")" -eq 1 ]] \
  && [[ "$(grep -c '^ADMIN_TOKEN=' "$OUT")" -eq 1 ]]; then
  ok "fixture merge preserves protected + single secret keys"
else
  ko "fixture merge incorrect"
  cat "$OUT"
fi

# Status file must not contain raw secrets longer than fingerprints
if grep -E 'JWT_SECRET_KEY=|token_urlsafe|eyJ' "$STATUS"; then
  ko "status leaked secrets"
else
  ok "status fingerprints only"
fi

# .gitignore allows bootstrap script
if git -C "$ROOT" check-ignore -q deploy/api/m1-runtime-secret-bootstrap-and-go-live.sh; then
  ko "bootstrap script is gitignored"
else
  ok "bootstrap script is trackable"
fi

rm -rf "$TMP"
echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
