#!/usr/bin/env bash
# Safety tests for M1 persistent tunnel + freeze helper (no real credentials).
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

SCR="${ROOT}/deploy/api/m1-persistent-tunnel-and-freeze.sh"
echo "ROOT=${ROOT}"

[[ -f "$SCR" ]] || { ko "script missing"; echo "FAILED=1"; exit 1; }
bash -n "$SCR" && ok "bash -n" || ko "bash -n"

non_comments="$(mktemp)"
grep -vE '^[[:space:]]*#' "$SCR" >"$non_comments" || true
bad=0
if grep -nE '\b(INSERT|UPDATE|DELETE FROM|DROP TABLE|ALTER TABLE)\b' "$non_comments"; then bad=1; fi
if grep -nE 'alembic[[:space:]]+(upgrade|downgrade)|seed_data\(|pg_restore|pg_dump' "$non_comments" \
  | grep -vE 'echo |NOTE|NEVER|MIGRATION_RUN=NO|abort|forbid'; then bad=1; fi
if grep -nE '\.env|JWT_SECRET|VAULT_FERNET|ADMIN_TOKEN|token_urlsafe|Fernet\.generate' "$non_comments" \
  | grep -vE 'echo |SECRET_REGENERATION=NO|ENV_OVERWRITE=NO|NEVER|abort|NOTE'; then
  # allow only ban markers
  if grep -nE 'token_urlsafe|Fernet\.generate|\.env.*>>|tee .*\.env' "$non_comments"; then bad=1; fi
fi
rm -f "$non_comments"
[[ "$bad" -eq 0 ]] && ok "no DB mutate / secret regen" || ko "forbidden ops"

for needle in \
  'com.guoqiao.cloudflared' \
  'com.guoqiao.caddy' \
  'guoqiao-api' \
  'api.guoqiaoplan.com' \
  'cloudflared tunnel login' \
  'PRODUCTION_FREEZE' \
  'RELOGIN_REQUIRED=YES' \
  'MIGRATION_RUN=NO' \
  'DATABASE_CHANGED=NO' \
  'reverse_proxy 127.0.0.1:8010'
do
  grep -qF "$needle" "$SCR" && ok "has $needle" || ko "missing $needle"
done

# Templates exist
for f in \
  "${ROOT}/deploy/api/launchd/com.guoqiao.cloudflared.plist.example" \
  "${ROOT}/deploy/api/launchd/com.guoqiao.caddy.plist.example" \
  "${ROOT}/deploy/api/PERSISTENT_TUNNEL.md"
do
  [[ -f "$f" ]] && ok "exists $(basename "$f")" || ko "missing $f"
done

# Must not commit credential patterns in templates
if grep -RInE '"AccountTag"|eyJ|"TunnelSecret"' \
  "${ROOT}/deploy/api/launchd" \
  "${ROOT}/deploy/api/cloudflared-config.example.yml" 2>/dev/null; then
  ko "credential-looking content in templates"
else
  ok "templates have no credential payloads"
fi

# Caddyfile upstream frozen
if grep -q 'reverse_proxy 127.0.0.1:8010' "${ROOT}/deploy/api/Caddyfile" \
  && ! grep -qE 'reverse_proxy 127.0.0.1:8000' "${ROOT}/deploy/api/Caddyfile"; then
  ok "Caddyfile upstream is only :8010"
else
  ko "Caddyfile upstream unexpected"
fi

echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
