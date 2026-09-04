#!/usr/bin/env bash
# ONE_SHOT: run ONCE on M1 from repo root after: git pull origin cursor/mobile-cloud-preview
# Completes: Caddy :8088 → SaaS :8010 + named Cloudflare Tunnel + DNS for api.guoqiaoplan.com
# Does NOT expose Postgres/SSH/8010/8088 publicly. Does NOT touch CNber.
# Does NOT require Free API :8000.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
TUNNEL_NAME="${TUNNEL_NAME:-guoqiao-api}"
HOSTNAME="${HOSTNAME:-api.guoqiaoplan.com}"
CADDY_ADDR="127.0.0.1:8088"
SAAS_ADDR="127.0.0.1:8010"

# H5 (huaqiao-app) ↔ SaaS real paths — keep acceptance aligned with saasApi.js / api.js
# students list: GET /api/students (auth required → 401/403 OK; 404 = route missing)
# students meta: GET /api/students/meta (public mount check)
# detail:      GET /api/students/{id}
# profile vault: GET /api/vault/profile (legacy; H5 also uses Master Profile via /api/students)
STUDENT_LIST_ENDPOINT="${STUDENT_LIST_ENDPOINT:-/api/students}"
STUDENT_META_ENDPOINT="${STUDENT_META_ENDPOINT:-/api/students/meta}"

http_code() {
  local method="$1" url="$2" data="${3:-}"
  if [[ -n "$data" ]]; then
    curl -sS -o /tmp/gq-probe-body.json -w '%{http_code}' -X "$method" "$url" \
      -H 'Content-Type: application/json' -d "$data" || echo "000"
  else
    curl -sS -o /tmp/gq-probe-body.json -w '%{http_code}' -X "$method" "$url" || echo "000"
  fi
}

classify_route() {
  # Sets: ROUTE_STATUS=OK|AUTH_REQUIRED|ROUTE_NOT_FOUND|BAD_GATEWAY|UNEXPECTED
  local code="$1"
  case "$code" in
    200) ROUTE_STATUS=OK ;;
    401|403) ROUTE_STATUS=AUTH_REQUIRED ;;
    422) ROUTE_STATUS=OK ;; # validation = route exists
    404) ROUTE_STATUS=ROUTE_NOT_FOUND ;;
    502|000) ROUTE_STATUS=BAD_GATEWAY ;;
    *) ROUTE_STATUS=UNEXPECTED ;;
  esac
}

discover_student_list_from_openapi() {
  local openapi_url="http://${SAAS_ADDR}/openapi.json"
  if ! curl -fsS "$openapi_url" -o /tmp/gq-openapi.json; then
    echo "WARN: openapi.json unreachable; keep STUDENT_LIST_ENDPOINT=${STUDENT_LIST_ENDPOINT}"
    return 0
  fi
  local discovered
  discovered="$(python3 - <<'PY'
import json
d=json.load(open("/tmp/gq-openapi.json"))
paths=d.get("paths") or {}
# Prefer exact list route used by H5
if "/api/students" in paths and "get" in paths["/api/students"]:
    print("/api/students")
elif "/api/vault/profile" in paths and "get" in paths["/api/vault/profile"]:
    print("/api/vault/profile")
else:
    # any get under /api/students*
    cands=sorted(p for p,ops in paths.items() if p.startswith("/api/students") and "get" in ops and "{" not in p)
    print(cands[0] if cands else "")
PY
)"
  if [[ -n "$discovered" ]]; then
    STUDENT_LIST_ENDPOINT="$discovered"
    echo "OPENAPI_STUDENT_LIST=${STUDENT_LIST_ENDPOINT}"
  else
    echo "ERROR: OpenAPI has no student list route — restart SaaS from current branch (need student_api)."
    exit 1
  fi
  if python3 - <<'PY'
import json,sys
d=json.load(open("/tmp/gq-openapi.json"))
sys.exit(0 if "/api/students/meta" in d.get("paths",{}) else 1)
PY
  then
    STUDENT_META_ENDPOINT="/api/students/meta"
  fi
}

echo "==> Preflight SaaS backend (:8010) — required"
curl -fsS "http://${SAAS_ADDR}/api/health" | tee /tmp/gq-saas.json
echo
discover_student_list_from_openapi

echo "==> Ensure caddy + cloudflared"
if ! command -v caddy >/dev/null; then
  if command -v brew >/dev/null; then brew install caddy; else echo "Install caddy first"; exit 1; fi
fi
if ! command -v cloudflared >/dev/null; then
  if command -v brew >/dev/null; then brew install cloudflare/cloudflare/cloudflared; else echo "Install cloudflared first"; exit 1; fi
fi

echo "==> Caddy loopback reverse proxy → SaaS :8010"
caddy stop >/dev/null 2>&1 || true
caddy start --config "$ROOT/deploy/api/Caddyfile" --adapter caddyfile
sleep 1

echo "==> Local acceptance (must be 200 via Caddy, upstream SaaS)"
code_saas="$(http_code GET "http://${SAAS_ADDR}/api/health")"
cp /tmp/gq-probe-body.json /tmp/gq-saas-health.json
code_caddy="$(http_code GET "http://${CADDY_ADDR}/api/health")"
cp /tmp/gq-probe-body.json /tmp/gq-caddy.json
echo "SAAS_HEALTH_HTTP=${code_saas}"
echo "CADDY_HEALTH_HTTP=${code_caddy}"
cat /tmp/gq-caddy.json; echo
test "${code_saas}" = "200"
test "${code_caddy}" = "200"

echo "==> Route smoke (401/403 = AUTH_REQUIRED OK; 404 = ROUTE_NOT_FOUND FAIL; 502 = BAD_GATEWAY FAIL)"
ACCEPT_FAIL=0

probe_accept() {
  local label="$1" method="$2" path="$3" data="${4:-}"
  local code
  code="$(http_code "$method" "http://${CADDY_ADDR}${path}" "$data")"
  classify_route "$code"
  echo "CADDY ${label} ${method} ${path} -> ${code} (${ROUTE_STATUS})"
  case "$ROUTE_STATUS" in
    OK|AUTH_REQUIRED) ;;
    ROUTE_NOT_FOUND)
      echo "ERROR: ROUTE_NOT_FOUND for ${path}"
      echo "HINT: H5 calls this path; if OpenAPI lists it but runtime is 404, restart uvicorn from repo HEAD so student_api is loaded."
      ACCEPT_FAIL=1
      ;;
    BAD_GATEWAY)
      echo "ERROR: BAD_GATEWAY/unreachable for ${path}"
      ACCEPT_FAIL=1
      ;;
    *)
      echo "ERROR: unexpected status ${code} for ${path}"
      ACCEPT_FAIL=1
      ;;
  esac
}

# Public / optional-auth catalog
probe_accept universities GET "/api/universities?target=international"
probe_accept timeline GET "/api/schedules?target=international"
probe_accept laws GET "/api/laws"
probe_accept policies GET "/api/policies"

# Student router mount (no auth) + list (auth)
if [[ -n "${STUDENT_META_ENDPOINT}" ]]; then
  probe_accept student_meta GET "${STUDENT_META_ENDPOINT}"
fi
probe_accept students GET "${STUDENT_LIST_ENDPOINT}"
probe_accept vault_profile GET "/api/vault/profile"

# Auth + history + eligibility (auth or validation)
probe_accept auth POST "/api/auth/login" '{"email":"x@example.com","password":"x"}'
probe_accept records GET "/api/records"
probe_accept elig_intl POST "/api/eligibility/international" '{"name":"probe"}'
probe_accept elig_hq POST "/api/eligibility/huaqiao" '{"name":"probe"}'

if [[ "${ACCEPT_FAIL}" -ne 0 ]]; then
  echo "ACCEPTANCE_FAILED=YES"
  exit 1
fi
echo "ACCEPTANCE_FAILED=NO"
echo "H5_STUDENT_ENDPOINT=/api/students"
echo "SAAS_STUDENT_ENDPOINT=${STUDENT_LIST_ENDPOINT}"
echo "CADDY_STUDENT_ENDPOINT=${STUDENT_LIST_ENDPOINT}"
echo "ENDPOINTS_ALIGNED=YES"

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
