#!/usr/bin/env bash
# M1 one-shot: expose existing local SaaS/Free backends via Cloudflare Tunnel.
# Does NOT expose Postgres/SSH/Tailscale. Does NOT migrate databases.
#
# Prerequisites on M1:
#   - SaaS backend listening (verify: curl -sS http://127.0.0.1:8010/api/health)
#   - Free backend listening (verify: curl -sS http://127.0.0.1:8000/api/health)  [optional but recommended]
#   - brew install caddy cloudflared   (or equivalent)
#   - cloudflared login   (once)
#
# Usage (from repo root on M1):
#   bash deploy/api/m1-go-live.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
API_DIR="$ROOT/deploy/api"
TUNNEL_NAME="${TUNNEL_NAME:-guoqiao-api}"
HOSTNAME="${HOSTNAME:-api.guoqiaoplan.com}"
CADDY_ADDR="${CADDY_ADDR:-127.0.0.1:8088}"

echo "==> Audit local backends (do not guess ports)"
if curl -fsS "http://127.0.0.1:8010/api/health" >/tmp/guoqiao-saas-health.json; then
  echo "SaaS :8010 OK $(cat /tmp/guoqiao-saas-health.json)"
else
  echo "ERROR: SaaS not reachable on 127.0.0.1:8010 — start it first, then re-run."
  exit 1
fi
if curl -fsS "http://127.0.0.1:8000/api/health" >/tmp/guoqiao-free-health.json; then
  echo "Free :8000 OK $(cat /tmp/guoqiao-free-health.json)"
else
  echo "WARN: Free :8000 not up — eligibility/history via free API will fail until started."
fi

echo "==> CORS reminder (set on both backends, then restart):"
echo "CORS_ORIGINS=https://app.guoqiaoplan.com,https://huaqiao-international-eligibility-system.rambolluk.workers.dev"

echo "==> Start Caddy on ${CADDY_ADDR} (loopback only)"
if ! curl -fsS "http://${CADDY_ADDR}/api/health" >/dev/null 2>&1; then
  caddy stop >/dev/null 2>&1 || true
  caddy start --config "$API_DIR/Caddyfile" --adapter caddyfile
  sleep 1
fi
curl -fsS "http://${CADDY_ADDR}/api/health" | tee /tmp/guoqiao-caddy-health.json
echo

echo "==> Ensure Cloudflare Tunnel ${TUNNEL_NAME} → http://${CADDY_ADDR}"
if ! cloudflared tunnel list 2>/dev/null | grep -q "${TUNNEL_NAME}"; then
  cloudflared tunnel create "${TUNNEL_NAME}"
fi
TUNNEL_ID="$(cloudflared tunnel list | awk -v n="$TUNNEL_NAME" '$2==n {print $1; exit}')"
CRED="$HOME/.cloudflared/${TUNNEL_ID}.json"
if [[ ! -f "$CRED" ]]; then
  echo "ERROR: missing credentials file $CRED"
  exit 1
fi

CFG="$HOME/.cloudflared/guoqiao-api.yml"
cat >"$CFG" <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${CRED}
ingress:
  - hostname: ${HOSTNAME}
    service: http://${CADDY_ADDR}
  - service: http_status:404
EOF

echo "==> Route DNS ${HOSTNAME} → tunnel (Cloudflare managed CNAME)"
cloudflared tunnel route dns "${TUNNEL_NAME}" "${HOSTNAME}" || true

echo "==> Run tunnel (foreground). Keep this terminal open, or install as a service."
echo "Verify: curl -sS https://${HOSTNAME}/api/health"
exec cloudflared tunnel --config "$CFG" run "${TUNNEL_NAME}"
