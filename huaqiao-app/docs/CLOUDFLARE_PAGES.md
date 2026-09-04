# Fixed H5 preview — Cloudflare Workers Static Assets (Workers Builds)
#
# Cloudflare Git Build (repo root):
#   Root directory = /
#   Build command  = None  (handled by wrangler.toml [build].command)
#   Deploy command = npx wrangler versions upload
#
# Wrangler config (repo root):
#   wrangler.toml → assets.directory = ./huaqiao-app/dist
#   [build].command = npm run build:h5
#
# Worker (existing Git-connected, do not delete):
#   huaqiao-international-eligibility-system
# Fixed URL:
#   https://huaqiao-international-eligibility-system.workers.dev
#
# Local:
#   npm install
#   npm run deploy:h5
#
# Never put Tailscale / LAN / localhost into VITE_API_BASE / VITE_SAAS_API.
#
# Production API (HTTPS):
#   VITE_API_BASE=https://api.guoqiaoplan.com
#   VITE_SAAS_API=https://api.guoqiaoplan.com
# See deploy/api/README.md for Cloudflare Tunnel + Caddy (M1) wiring.
# API must NOT be deployed into this H5 Worker.
