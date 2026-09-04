#!/usr/bin/env bash
# ONE_SHOT: run ONCE on M1 from repo root after: git pull origin cursor/mobile-cloud-preview
# Completes: Caddy :8088 + named Cloudflare Tunnel + DNS for api.guoqiaoplan.com
# Does NOT expose Postgres/SSH/8010/8088 publicly. Does NOT touch CNber.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TUNNEL_NAME="${TUNNEL_NAME:-guoqiao-api}"
HOSTNAME="${HOSTNAME:-api.guoqiaoplan.com}"
CADDY_ADDR="127.0.0.1:8088"

need() { command -v "$1" >/dev/null || { echo "MISSING:$1"; exit 1; }; }

echo "==> Preflight backends"
curl -fsS "http://127.0.0.1:8010/api/health" | tee /tmp/gq-saas.json
echo
if ! curl -fsS "http://127.0.0.1:8000/api/health" >/tmp/gq-free.json; then
  echo "WARN: Free API :8000 down (eligibility/history via free path). Continue with SaaS-only routes."
else
  cat /tmp/gq-free.json; echo
fi

echo "==> Ensure caddy + cloudflared"
if ! command -v caddy >/dev/null; then
  if command -v brew >/dev/null; then brew install caddy; else echo "Install caddy first"; exit 1; fi
fi
if ! command -v cloudflared >/dev/null; then
  if command -v brew >/dev/null; then brew install cloudflare/cloudflare/cloudflared; else echo "Install cloudflared first"; exit 1; fi
fi

echo "==> Caddy loopback reverse proxy"
caddy stop >/dev/null 2>&1 || true
caddy start --config "$ROOT/deploy/api/Caddyfile" --adapter caddyfile
sleep 1
curl -fsS "http://${CADDY_ADDR}/api/health" | tee /tmp/gq-caddy.json
echo

echo "==> Cloudflare named tunnel + DNS (browser login only if first time)"
if ! cloudflared tunnel list 2>/dev/null | awk '{print $2}' | grep -qx "$TUNNEL_NAME"; then
  cloudflared tunnel login || true
  cloudflared tunnel create "$TUNNEL_NAME"
fi
TUNNEL_ID="$(cloudflared tunnel list | awk -v n="$TUNNEL_NAME" '$2==n{print $1; exit}')"
CRED="$HOME/.cloudflared/${TUNNEL_ID}.json"
test -f "$CRED"
CFG="$HOME/.cloudflared/guoqiao-api.yml"
cat >"$CFG" <<EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${CRED}
ingress:
  - hostname: ${HOSTNAME}
    service: http://${CADDY_ADDR}
  - service: http_status:404
EOF
cloudflared tunnel route dns "$TUNNEL_NAME" "$HOSTNAME" || true

echo "==> Starting tunnel (keep running). Health: https://${HOSTNAME}/api/health"
nohup cloudflared tunnel --config "$CFG" run "$TUNNEL_NAME" >/tmp/gq-tunnel.log 2>&1 &
echo $! >/tmp/gq-tunnel.pid
sleep 5
for i in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "https://${HOSTNAME}/api/health" >/tmp/gq-pub-health.json; then
    echo "PUBLIC_HEALTH_OK"; cat /tmp/gq-pub-health.json; echo; exit 0
  fi
  sleep 3
done
echo "Tunnel started but public health not yet OK — check /tmp/gq-tunnel.log"
tail -n 40 /tmp/gq-tunnel.log || true
exit 1
