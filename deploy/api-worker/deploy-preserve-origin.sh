#!/usr/bin/env bash
# Safely redeploy guoqiao-api Worker while preserving BACKEND_ORIGIN plain_text binding.
# Optional override (do not commit secrets/ephemeral URLs into wrangler.toml):
#   BACKEND_ORIGIN=https://<tunnel-id>.cfargotunnel.com bash deploy/api-worker/deploy-preserve-origin.sh
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

abort() { echo "ABORT: $*" >&2; exit 1; }

resolve_live_origin() {
  local ver origin acct
  ver="$(npx wrangler deployments list 2>/dev/null | awk '/Version\(s\):/{getline; print $NF; exit}')"
  [[ -n "${ver}" ]] || ver="$(npx wrangler versions list 2>/dev/null | awk '/^Version ID:/{print $3}' | tail -1)"
  [[ -n "${ver}" ]] || abort "cannot resolve current worker version"
  origin="$(npx wrangler versions view "${ver}" 2>/dev/null | sed -n 's/.*env.BACKEND_ORIGIN ("\([^"]*\)").*/\1/p' | head -1)"
  if [[ -z "${origin}" || "${origin}" == *...* ]]; then
    acct="${CLOUDFLARE_ACCOUNT_ID:-}"
    [[ -n "${acct}" ]] || abort "CLOUDFLARE_ACCOUNT_ID required to resolve full BACKEND_ORIGIN"
    origin="$(curl -sS -H "Authorization: Bearer ${CLOUDFLARE_API_TOKEN}" \
      "https://api.cloudflare.com/client/v4/accounts/${acct}/workers/scripts/guoqiao-api/versions/${ver}" \
      | python3 -c 'import sys,json; d=json.load(sys.stdin); bs=(d.get("result") or {}).get("resources",{}).get("bindings") or [];
print(next((b.get("text") for b in bs if b.get("name")=="BACKEND_ORIGIN"), ""))')"
  fi
  printf '%s' "${origin}"
}

if [[ -n "${BACKEND_ORIGIN:-}" ]]; then
  ORIGIN="${BACKEND_ORIGIN}"
  echo "BACKEND_ORIGIN_SOURCE=ENV_OVERRIDE"
else
  ORIGIN="$(resolve_live_origin)"
  echo "BACKEND_ORIGIN_SOURCE=LIVE_PRESERVE"
fi

[[ -n "${ORIGIN}" ]] || abort "BACKEND_ORIGIN missing — refuse deploy that would 1101"
echo "BACKEND_ORIGIN_HOST=$(echo "${ORIGIN}" | sed -E 's#https?://##; s#/.*##')"
echo "PRESERVE_BACKEND_ORIGIN=YES"

npx wrangler deploy --var "BACKEND_ORIGIN:${ORIGIN}"
echo "DEPLOY=PASS"
