# Cloudflare Workers / Pages — guoqiao-mobile-preview (H5 fixed preview)
#
# Product: Workers Static Assets (unified platform; not the mistaken Worker
# `huaqiao-international-eligibility-system`).
#
# Auto-deploy: GitHub Actions on push to `cursor/mobile-cloud-preview`
#   workflow: .github/workflows/deploy-h5-preview.yml
#   secrets (repo): CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID
#
# Local / CI deploy (after npm run build):
#   npx wrangler deploy
#
# Fixed URL (after first successful deploy):
#   https://guoqiao-mobile-preview.workers.dev
#
# Build (run from huaqiao-app/):
#   npm ci && npm run build  →  dist/
#
# Env (Preview / Production build vars — HTTPS only, never Tailscale/LAN):
#   VITE_API_BASE=
#   VITE_SAAS_API=
#
# SPA fallback: wrangler.toml assets.not_found_handling = single-page-application
# Also keep public/_redirects for Pages compatibility if Git Pages is used later.
