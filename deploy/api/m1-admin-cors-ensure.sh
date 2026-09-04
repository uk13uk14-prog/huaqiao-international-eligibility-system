#!/usr/bin/env bash
# M1 — ensure production CORS allows https://admin.guoqiaoplan.com then kickstart SaaS.
# No DB writes, no migration, no tunnel/Caddy/secret changes.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
ENV_FILE="${BACKEND}/.env"
ADMIN_ORIGIN="https://admin.guoqiaoplan.com"
APP_ORIGIN="https://app.guoqiaoplan.com"
SAAS_LABEL="com.guoqiao.saas-backend"
SAAS_ADDR="127.0.0.1:8010"

abort() { echo "ABORT: $*" >&2; exit 1; }

[[ -f "${ENV_FILE}" ]] || abort "missing ${ENV_FILE}"

python3 - "$ENV_FILE" "$ADMIN_ORIGIN" "$APP_ORIGIN" <<'PY'
from pathlib import Path
import sys
env_path = Path(sys.argv[1])
admin, app = sys.argv[2], sys.argv[3]
lines = env_path.read_text().splitlines()
out, found = [], False
for line in lines:
    if line.startswith("CORS_ORIGINS="):
        found = True
        val = line.split("=", 1)[1].strip().strip('"').strip("'")
        parts = [x.strip() for x in val.split(",") if x.strip()]
        for o in (admin, app, "https://huaqiao-international-eligibility-system.rambolluk.workers.dev"):
            if o not in parts:
                parts.append(o)
        out.append("CORS_ORIGINS=" + ",".join(parts))
        print("CORS_ORIGINS_HAS_ADMIN=", "YES" if admin in parts else "NO")
        # redact any accidental secrets — only print hostnames
        hosts = []
        for p in parts:
            if "://" in p:
                hosts.append(p.split("://", 1)[1].split("/")[0])
            else:
                hosts.append(p)
        print("CORS_HOSTS=", ",".join(hosts))
    else:
        out.append(line)
if not found:
    out.append(f"CORS_ORIGINS={app},{admin}")
    print("CORS_ORIGINS_HAS_ADMIN=YES")
env_path.write_text("\n".join(out) + "\n")
print("CORS_FILE_UPDATED=YES")
print("SECRET_CHANGED=NO")
PY

launchctl kickstart -k "gui/$(id -u)/${SAAS_LABEL}" || abort "kickstart failed"
sleep 3
HC="$(curl -sS -o /dev/null -w '%{http_code}' --connect-timeout 5 "http://${SAAS_ADDR}/api/health" || echo 000)"
[[ "${HC}" == "200" ]] || abort "health after kickstart != 200"

# Local CORS probe (Origin reflection)
HDR="$(curl -sS -D - -o /dev/null --connect-timeout 5 \
  -X OPTIONS "http://${SAAS_ADDR}/api/auth/login" \
  -H "Origin: ${ADMIN_ORIGIN}" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,authorization" || true)"
echo "$HDR" | grep -qi "access-control-allow-origin: ${ADMIN_ORIGIN}" \
  && echo "CORS_ADMIN_ORIGIN=PASS" \
  || { echo "CORS_ADMIN_ORIGIN=FAIL"; echo "$HDR" | grep -i access-control || true; abort "ACAO missing for admin origin"; }

# admin/v1 must be mounted on the running binary
ME="$(curl -sS -o /dev/null -w '%{http_code}' "http://${SAAS_ADDR}/api/admin/v1/me" || echo 000)"
DASH="$(curl -sS -o /dev/null -w '%{http_code}' "http://${SAAS_ADDR}/api/admin/v1/dashboard" || echo 000)"
echo "ADMIN_V1_ME_HTTP=${ME}"
echo "ADMIN_V1_DASHBOARD_HTTP=${DASH}"
[[ "${ME}" != "404" && "${DASH}" != "404" ]] || abort "admin/v1 still 404 on :8010 — pull cursor/mobile-cloud-preview and kickstart again"

echo "TUNNEL_CHANGED=NO"
echo "CADDY_CHANGED=NO"
echo "DATABASE_CHANGED=NO"
echo "NEXT=Hard-refresh https://admin.guoqiaoplan.com and login"
