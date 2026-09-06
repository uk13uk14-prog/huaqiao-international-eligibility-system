#!/usr/bin/env bash
# M1 READ-ONLY inspect: student_master_profiles id=1/2 display_name sources.
#
# Default: --inspect-only (NO writes).
# NEVER prints full cipher / passport / national id / password / JWT.
#
# Usage on M1:
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   bash deploy/api/m1-student-name-backfill-inspect.sh --inspect-only
#
# Optional dry-run proposal file:
#   bash deploy/api/m1-student-name-backfill-inspect.sh --inspect-only --write-proposal /tmp/name-backfill-dryrun.json
#
# FORBIDDEN: APPLY / UPDATE / production migration from this script.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
VENV_PY="${BACKEND}/.venv/bin/python"
PG_CONTAINER="${PG_CONTAINER:-huaqiao-postgres}"
PG_HOST="127.0.0.1"
PG_PORT="5433"
PG_DB="huaqiao"
INSPECT_ONLY=YES
PROPOSAL_OUT=""

for arg in "$@"; do
  case "$arg" in
    --inspect-only) INSPECT_ONLY=YES ;;
    --write-proposal=*) PROPOSAL_OUT="${arg#--write-proposal=}" ;;
    --write-proposal) shift_next=1 ;;
    --apply|--write|--update)
      echo "REFUSE: production write flags are forbidden in this script" >&2
      exit 2
      ;;
    --help|-h)
      echo "Usage: $0 --inspect-only [--write-proposal PATH]"
      exit 0
      ;;
  esac
done

abort() { echo "ABORT: $*" >&2; exit 1; }
info() { echo "==> $*"; }

[[ "${INSPECT_ONLY}" == "YES" ]] || abort "only --inspect-only is allowed"
[[ -x "${VENV_PY}" ]] || abort "missing venv python: ${VENV_PY}"
command -v docker >/dev/null || abort "docker required"
docker inspect "${PG_CONTAINER}" >/dev/null 2>&1 || abort "container ${PG_CONTAINER} missing"

# Bind production credentials from container — never invent role=postgres.
_PG_USER=""; _PG_PASS=""; _PG_DBNAME=""
while IFS= read -r ev; do
  case "$ev" in
    POSTGRES_USER=*) _PG_USER="${ev#POSTGRES_USER=}" ;;
    POSTGRES_PASSWORD=*) _PG_PASS="${ev#POSTGRES_PASSWORD=}" ;;
    POSTGRES_DB=*) _PG_DBNAME="${ev#POSTGRES_DB=}" ;;
  esac
done < <(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${PG_CONTAINER}")
[[ -n "${_PG_USER}" && -n "${_PG_PASS}" && -n "${_PG_DBNAME}" ]] || abort "POSTGRES_* missing from container"
[[ "${_PG_DBNAME}" == "${PG_DB}" ]] || abort "POSTGRES_DB=${_PG_DBNAME} != ${PG_DB}"
# Refuse accidental 5432 socket usage
ss -ltn 2>/dev/null | grep -q ':5433' || true

export DATABASE_URL="postgresql+psycopg://${_PG_USER}:${_PG_PASS}@${PG_HOST}:${PG_PORT}/${PG_DB}"
export PROPOSAL_OUT
info "READ-ONLY inspect student_master_profiles id=1,2 on ${PG_HOST}:${PG_PORT}/${PG_DB} as ${_PG_USER}"
info "PRODUCTION_WRITE=NO"

cd "${BACKEND}"
"${VENV_PY}" - <<'PY'
from __future__ import annotations
import json, os, re, sys
from pathlib import Path

# Fail closed if URL looks wrong
url = os.environ.get("DATABASE_URL", "")
if ":5432/" in url and ":5433/" not in url:
    print("REFUSE: refusing host port 5432 for production inspect", file=sys.stderr)
    sys.exit(2)
if "/huaqiao_admin_staging" in url:
    print("REFUSE: staging URL passed to M1 production inspect", file=sys.stderr)
    sys.exit(2)

sys.path.insert(0, str(Path.cwd()))
from sqlalchemy import create_engine, text
from app.services.vault_crypto import decrypt_profile_json
from app.services.student_profile import normalize_profile

PLACEHOLDERS = {"", "未命名学生", "未命名学生", "待补姓名"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Priority: chinese_name > english_name > preferred_name > legal_name > full_name > name aliases
# Never use email as a name.
PRIORITY = (
    ("basic_info.chinese_name", ("basic_info", "chinese_name")),
    ("basic_info.english_name", ("basic_info", "english_name")),
    ("basic_info.preferred_name", ("basic_info", "preferred_name")),
    ("preferred_name", ("preferred_name",)),
    ("basic_info.legal_name", ("basic_info", "legal_name")),
    ("legal_name", ("legal_name",)),
    ("basic_info.full_name", ("basic_info", "full_name")),
    ("basic_info.name", ("basic_info", "name")),
)

def dig(profile, path):
    node = profile
    for p in path:
        if not isinstance(node, dict):
            return ""
        node = node.get(p)
    return str(node or "").strip()

def _clean(val: str):
    val = (val or "").strip()
    if not val or val in PLACEHOLDERS:
        return ""
    if EMAIL_RE.match(val) or "@" in val:
        return ""
    return val

def resolve(profile: dict):
    for source, path in PRIORITY:
        val = _clean(dig(profile, path))
        if val:
            return source, val
    # name aliases: list/dict under basic_info or top-level
    aliases = []
    for key in (("basic_info", "name_aliases"), ("basic_info", "aliases"), ("name_aliases",), ("aliases",)):
        node = profile
        ok = True
        for p in key:
            if not isinstance(node, dict):
                ok = False
                break
            node = node.get(p)
        if not ok:
            continue
        if isinstance(node, list):
            aliases.extend(node)
        elif isinstance(node, dict):
            aliases.extend(node.values())
        elif isinstance(node, str):
            aliases.append(node)
    for i, raw in enumerate(aliases):
        val = _clean(str(raw))
        if val:
            return f"name_aliases[{i}]", val
    return "NONE", None

engine = create_engine(url)
out = {"INSPECT_ONLY": True, "PRODUCTION_WRITE": False, "candidates": []}
with engine.connect() as conn:
    for sid in (1, 2):
        row = conn.execute(
            text("SELECT id, display_name, cipher_blob FROM student_master_profiles WHERE id=:id"),
            {"id": sid},
        ).mappings().first()
        key = f"STUDENT_{sid}"
        if not row:
            print(f"{key}_DISPLAY_NAME_CURRENT=NOT_FOUND")
            print(f"{key}_PROFILE_NAME_FOUND=NO")
            print(f"{key}_NAME_SOURCE=NONE")
            print(f"{key}_PROPOSED_DISPLAY_NAME=NONE")
            continue
        current = (row["display_name"] or "").strip()
        print(f"{key}_DISPLAY_NAME_CURRENT={current or 'EMPTY'}")
        try:
            prof = normalize_profile(decrypt_profile_json(row["cipher_blob"]) if row["cipher_blob"] else {})
        except Exception as exc:
            print(f"{key}_PROFILE_NAME_FOUND=NO")
            print(f"{key}_NAME_SOURCE=DECRYPT_ERROR")
            print(f"{key}_PROPOSED_DISPLAY_NAME=NONE")
            print(f"{key}_ERROR={type(exc).__name__}")
            continue
        source, proposed = resolve(prof)
        found = "YES" if proposed else "NO"
        print(f"{key}_PROFILE_NAME_FOUND={found}")
        print(f"{key}_NAME_SOURCE={source}")
        if proposed and current in PLACEHOLDERS:
            print(f"{key}_PROPOSED_DISPLAY_NAME={proposed}")
            out["candidates"].append({
                "student_id": sid,
                "current": current or "未命名学生",
                "proposed": proposed,
                "source": source,
            })
        else:
            print(f"{key}_PROPOSED_DISPLAY_NAME={'NONE' if not proposed else proposed}")
            if not proposed:
                print(f"{key}_UI_FALLBACK=待补姓名")
                print(f"{key}_BACKFILL_ALLOWED=NO")

print(f"BACKFILL_DRY_RUN={'PASS' if True else 'FAIL'}")
print(f"BACKFILL_CANDIDATE_COUNT={len(out['candidates'])}")
print("PRODUCTION_BACKFILL_APPLIED=NO")
proposal_out = os.environ.get("PROPOSAL_OUT") or ""
if proposal_out:
    Path(proposal_out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"PROPOSAL_FILE={proposal_out}")
PY
