#!/usr/bin/env bash
# M1 READ-ONLY runtime secret discovery.
# Finds JWT_SECRET_KEY / VAULT_FERNET_KEY / ADMIN_TOKEN used by prior :8010.
# NEVER prints secret values — only FOUND/SOURCE/FINGERPRINT (sha256[:12]).
# NEVER invents secrets. NEVER migrates DB. NEVER starts backend.
#
# Usage:
#   cd /Users/agent001/deploy/huaqiao-international-eligibility-system
#   bash deploy/api/m1-runtime-secret-discover.sh
set -u
# NOT set -e — probe failures must not abort discovery

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND="${ROOT}/huaqiao-saas-pro/backend"
STATE_DIR="${HOME}/.guoqiao/saas"
PLAN_FILE="${STATE_DIR}/secret-restore.plan"
mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}" 2>/dev/null || true

section() { echo; echo "======== $* ========"; }
note() { echo "NOTE: $*"; }
warn() { echo "WARN: $*"; }

fingerprint() {
  # stdin -> sha256 first 12 hex chars; empty -> EMPTY
  local v
  v="$(cat)"
  if [[ -z "$v" ]]; then
    echo "EMPTY"
    return 0
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s' "$v" | sha256sum | awk '{print substr($1,1,12)}'
  elif command -v shasum >/dev/null 2>&1; then
    printf '%s' "$v" | shasum -a 256 | awk '{print substr($1,1,12)}'
  else
    python3 -c 'import hashlib,sys; print(hashlib.sha256(sys.stdin.buffer.read()).hexdigest()[:12])' <<<"$v"
  fi
}

# Validate JWT candidate (non-empty, not placeholder)
jwt_ok() {
  local v="$1"
  [[ -n "$v" ]] || return 1
  [[ "$v" != "change-me-in-production" ]] || return 1
  [[ "${#v}" -ge 8 ]] || return 1
  return 0
}

vault_ok() {
  local v="$1"
  [[ -n "$v" ]] || return 1
  # Fernet format check — never print key
  GUOQIAO_CAND="$v" python3 - <<'PY' 2>/dev/null
import os, sys, base64
k = os.environ["GUOQIAO_CAND"].encode("utf-8")
try:
    from cryptography.fernet import Fernet
    Fernet(k)
except ImportError:
    try:
        raw = base64.urlsafe_b64decode(k)
    except Exception:
        sys.exit(1)
    if len(raw) != 32:
        sys.exit(1)
except Exception:
    sys.exit(1)
sys.exit(0)
PY
}

admin_ok() {
  local v="$1"
  [[ -n "$v" ]] || return 1
  [[ "${#v}" -ge 4 ]] || return 1
  return 0
}

# Candidate lists: pipe-separated "source|value" (value never echoed)
JWT_CANDS=""
VAULT_CANDS=""
ADMIN_CANDS=""

add_cand() {
  # $1=kind jwt|vault|admin  $2=source  $3=value
  local kind="$1" src="$2" val="$3"
  [[ -n "$val" ]] || return 0
  # strip quotes/CR
  val="$(printf '%s' "$val" | tr -d '\r' | sed -E 's/^[[:space:]]+//;s/[[:space:]]+$//;s/^["'\'']//;s/["'\'']$//')"
  case "$kind" in
    jwt)
      jwt_ok "$val" || return 0
      if [[ -z "$JWT_CANDS" ]]; then JWT_CANDS="${src}|${val}"; else JWT_CANDS="${JWT_CANDS}"$'\n'"${src}|${val}"; fi
      ;;
    vault)
      vault_ok "$val" || return 0
      if [[ -z "$VAULT_CANDS" ]]; then VAULT_CANDS="${src}|${val}"; else VAULT_CANDS="${VAULT_CANDS}"$'\n'"${src}|${val}"; fi
      ;;
    admin)
      admin_ok "$val" || return 0
      if [[ -z "$ADMIN_CANDS" ]]; then ADMIN_CANDS="${src}|${val}"; else ADMIN_CANDS="${ADMIN_CANDS}"$'\n'"${src}|${val}"; fi
      ;;
  esac
}

extract_from_text() {
  # $1=source_label  $2=file path — scan KEY=value lines / export KEY=value
  local src="$1" f="$2"
  [[ -f "$f" && -r "$f" ]] || return 0
  # Use python to parse without printing secrets
  GUOQIAO_SRC="$src" GUOQIAO_FILE="$f" python3 - <<'PY' 2>/dev/null || true
import os, re, sys
path = os.environ["GUOQIAO_FILE"]
src = os.environ["GUOQIAO_SRC"]
try:
    raw = open(path, "r", encoding="utf-8", errors="ignore").read()
except Exception:
    sys.exit(0)
# patterns: KEY=val, export KEY=val, KEY: val (plist-ish)
keys = {
    "jwt": [r"JWT_SECRET_KEY", r"JWT_SECRET\b", r"(?<![A-Z_])SECRET_KEY(?![A-Z_])"],
    "vault": [r"VAULT_FERNET_KEY", r"FERNET_KEY\b"],
    "admin": [r"ADMIN_TOKEN"],
}
out = []
for kind, pats in keys.items():
    for pat in pats:
        for m in re.finditer(
            rf"(?im)(?:export\s+)?(?:{pat})\s*[=:]\s*([^\n\r#]+)",
            raw,
        ):
            val = m.group(1).strip().strip('"').strip("'")
            if val:
                # emit kind|src|len only via a side channel file descriptor? 
                # Instead write null-safe to a temp via stdout as base64 length-prefixed NO — parent needs values.
                # Parent invokes python per-file and collects via structured lines KIND\tSRC\tB64
                import base64
                b = base64.b64encode(val.encode("utf-8")).decode("ascii")
                print(f"{kind}\t{src}\t{b}")
PY
}

ingest_python_hits() {
  # read KIND\tSRC\tB64 lines from stdin
  local kind src b64 val
  while IFS=$'\t' read -r kind src b64; do
    [[ -n "$kind" && -n "$b64" ]] || continue
    val="$(printf '%s' "$b64" | python3 -c 'import sys,base64; sys.stdout.buffer.write(base64.b64decode(sys.stdin.read().strip()))' 2>/dev/null || true)"
    [[ -n "$val" ]] || continue
    add_cand "$kind" "$src" "$val"
  done
}

echo "============================================================"
echo "GUOQIAO M1 RUNTIME SECRET DISCOVERY"
echo "READ_ONLY=YES"
echo "SECRET_OUTPUT_REDACTED=YES"
echo "DATABASE_CHANGED=NO"
echo "ROOT=${ROOT}"
echo "============================================================"

section "1 shell profiles / history"
for f in \
  "${HOME}/.zsh_history" "${HOME}/.zshrc" "${HOME}/.zprofile" "${HOME}/.profile" \
  "${HOME}/.bash_profile" "${HOME}/.bashrc" "${HOME}/.history"
do
  if [[ -f "$f" ]]; then
    echo "SCAN $f"
    extract_from_text "file:$f" "$f" | ingest_python_hits
  else
    echo "ABSENT $f"
  fi
done

section "2 LaunchAgents / LaunchDaemons"
if [[ -d "${HOME}/Library/LaunchAgents" ]]; then
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    echo "SCAN $f"
    extract_from_text "launchagent:$f" "$f" | ingest_python_hits
  done < <(find "${HOME}/Library/LaunchAgents" -type f \( -name '*.plist' -o -name '*guoqiao*' -o -name '*huaqiao*' -o -name '*saas*' \) 2>/dev/null | head -n 80)
else
  echo "LaunchAgents=ABSENT"
fi
if [[ -d /Library/LaunchDaemons ]]; then
  if ls /Library/LaunchDaemons >/dev/null 2>&1; then
    while IFS= read -r f; do
      [[ -f "$f" ]] || continue
      echo "SCAN $f"
      extract_from_text "launchdaemon:$f" "$f" | ingest_python_hits
    done < <(find /Library/LaunchDaemons -type f \( -name '*guoqiao*' -o -name '*huaqiao*' -o -name '*saas*' \) 2>/dev/null | head -n 40)
  else
    echo "LaunchDaemons=SKIPPED (no permission)"
  fi
else
  echo "LaunchDaemons=ABSENT"
fi

section "3 ~/.guoqiao and ~/.config"
for d in "${HOME}/.guoqiao" "${HOME}/.config/guoqiao" "${HOME}/.config"; do
  [[ -d "$d" ]] || continue
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    case "$f" in
      *.dump|*.db|*.sqlite*|*.log.gz) continue ;;
    esac
    echo "SCAN $f"
    extract_from_text "state:$f" "$f" | ingest_python_hits
  done < <(find "$d" -maxdepth 4 -type f \( -name '*.env*' -o -name '*secret*' -o -name '*runtime*' -o -name '*.plist' -o -name '*.yml' -o -name '*.yaml' -o -name '*.sh' -o -name '*.txt' -o -name '*.json' \) 2>/dev/null | head -n 100)
done

section "4 repo ignored .env* and deploy"
# Do NOT print .env contents
for f in \
  "${BACKEND}/.env" \
  "${BACKEND}/.env.local" \
  "${BACKEND}/.env.production" \
  "${ROOT}/.env" \
  "${ROOT}/huaqiao-saas-pro/.env"
do
  if [[ -f "$f" ]]; then
    echo "SCAN present $(echo "$f" | sed "s#^${ROOT}/#repo:#;s#^${HOME}/#home:#")"
    extract_from_text "envfile:$f" "$f" | ingest_python_hits
  fi
done
while IFS= read -r f; do
  [[ -f "$f" ]] || continue
  echo "SCAN deploy:$(echo "$f" | sed "s#^${ROOT}/##")"
  extract_from_text "deploy:$f" "$f" | ingest_python_hits
done < <(find "${ROOT}/deploy" -type f \( -name '*.env*' -o -name '*.example' -o -name '*.sh' -o -name '*.md' -o -name '*.yml' \) 2>/dev/null | head -n 80)

section "5 nohup / logs (bounded)"
for f in /tmp/gq-*.log /tmp/gq-*.err "${HOME}/.guoqiao/saas/logs"/*.log; do
  [[ -f "$f" ]] || continue
  echo "SCAN log:$f"
  extract_from_text "log:$f" "$f" | ingest_python_hits
done

section "6 Docker env (huaqiao-postgres / compose only — no CNber)"
if command -v docker >/dev/null 2>&1; then
  if docker inspect huaqiao-postgres >/dev/null 2>&1; then
    # Only look for JWT/VAULT/ADMIN in env — postgres rarely has them
    docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' huaqiao-postgres 2>/dev/null \
      | grep -E 'JWT_SECRET|VAULT_FERNET|ADMIN_TOKEN|FERNET_KEY|SECRET_KEY' \
      | while IFS= read -r line; do
          case "$line" in
            JWT_SECRET_KEY=*|JWT_SECRET=*) add_cand jwt "docker:huaqiao-postgres" "${line#*=}" ;;
            VAULT_FERNET_KEY=*|FERNET_KEY=*) add_cand vault "docker:huaqiao-postgres" "${line#*=}" ;;
            ADMIN_TOKEN=*) add_cand admin "docker:huaqiao-postgres" "${line#*=}" ;;
            SECRET_KEY=*) add_cand jwt "docker:huaqiao-postgres:SECRET_KEY" "${line#*=}" ;;
          esac
        done || true
    echo "DOCKER_INSPECT=huaqiao-postgres (JWT/VAULT/ADMIN keys scanned; values redacted)"
  else
    echo "DOCKER_INSPECT=huaqiao-postgres ABSENT"
  fi
  for cf in "${ROOT}/docker-compose.yml" "${ROOT}/docker-compose.yaml"; do
    [[ -f "$cf" ]] || continue
    extract_from_text "compose:$cf" "$cf" | ingest_python_hits
  done
else
  echo "docker=ABSENT"
fi

section "7 git stash (READ ONLY — no pop/apply/drop)"
if git -C "$ROOT" stash list >/dev/null 2>&1; then
  git -C "$ROOT" stash list 2>/dev/null | head -n 20 || true
  i=0
  while IFS= read -r sref; do
    [[ -n "$sref" ]] || continue
    i=$((i + 1))
    [[ $i -le 5 ]] || break
    # Show names of changed files only
    git -C "$ROOT" stash show --name-only "$sref" 2>/dev/null | head -n 30 || true
    # If stash touches .env, extract via show (binary-safe best effort)
    if git -C "$ROOT" stash show --name-only "$sref" 2>/dev/null | grep -E '\.env' >/dev/null; then
      tmp="$(mktemp)"
      git -C "$ROOT" stash show -p "$sref" -- "*.env" "*env*" 2>/dev/null | head -c 200000 >"$tmp" || true
      extract_from_text "stash:${sref}" "$tmp" | ingest_python_hits
      rm -f "$tmp"
    fi
  done < <(git -C "$ROOT" stash list --format='%gd' 2>/dev/null || true)
else
  echo "stash=unavailable"
fi
echo "STASH_TOUCH=NO"

section "8 git history (bounded pickaxe; values never printed)"
git -C "$ROOT" log -n 20 --all --oneline --grep='JWT_SECRET\|VAULT_FERNET\|ADMIN_TOKEN' -i 2>/dev/null | head -n 20 || true
git -C "$ROOT" log -n 15 --all --diff-filter=A --summary -- '*.env' 2>/dev/null | head -n 40 || true
# Bounded pickaxe: extract KEY=value from added lines only; never echo values
tmp_git="$(mktemp)"
for key in JWT_SECRET_KEY VAULT_FERNET_KEY ADMIN_TOKEN JWT_SECRET FERNET_KEY; do
  git -C "$ROOT" log --all -S"$key" -p --max-count=20 -G"$key" 2>/dev/null     | grep -aE "^\+.*(export[[:space:]]+)?${key}="     | sed 's/^+//'     | head -n 40 >>"$tmp_git" || true
done
# Also scan any historically added .env-like paths (content via show, capped)
while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  git -C "$ROOT" log --all --pretty=format:%H -- "$path" 2>/dev/null | head -n 5 | while read -r rev; do
    [[ -n "$rev" ]] || continue
    git -C "$ROOT" show "${rev}:${path}" 2>/dev/null | head -c 100000 >>"$tmp_git" || true
    printf '\n' >>"$tmp_git"
  done
done < <(git -C "$ROOT" log --all --diff-filter=A --name-only --pretty=format: -- '*.env' '.env' '.env.*' 2>/dev/null | sort -u | head -n 20)
if [[ -s "$tmp_git" ]]; then
  extract_from_text "git_hist" "$tmp_git" | ingest_python_hits
  echo "GIT_HIST_SCAN=YES (values redacted)"
else
  echo "GIT_HIST_SCAN=NO_HITS"
fi
rm -f "$tmp_git"

section "9 backups / archives (config-like only)"
for d in "${HOME}/guoqiao-backups" "${HOME}/.guoqiao/backups" "${ROOT}/db_backups"; do
  [[ -d "$d" ]] || continue
  while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    case "$f" in
      *.dump|*.sql|*.fc) continue ;; # never scan DB dumps for secrets as text blobs large; skip
      *.env*|*.txt|*.yml|*.yaml|*.sh|*.conf)
        echo "SCAN backup:$f"
        extract_from_text "backup:$f" "$f" | ingest_python_hits
        ;;
    esac
  done < <(find "$d" -maxdepth 3 -type f 2>/dev/null | head -n 50)
done

# ---------- Deduplicate by fingerprint ----------
summarize_kind() {
  local kind="$1" blob="$2" label="$3"
  local found=NO srcs="" fps="" uniq=0
  local line src val fp seen_fps=""
  if [[ -z "$blob" ]]; then
    echo "${label}_FOUND=NO"
    echo "${label}_SOURCE="
    echo "${label}_FINGERPRINT="
    echo "${label}_CANDIDATE_COUNT=0"
    echo "${label}_UNIQUE=NO"
    return 0
  fi
  while IFS= read -r line; do
    [[ -n "$line" ]] || continue
    src="${line%%|*}"
    val="${line#*|}"
    fp="$(printf '%s' "$val" | fingerprint)"
    found=YES
    if [[ -z "$srcs" ]]; then srcs="$src"; else srcs="${srcs};${src}"; fi
    if [[ -z "$fps" ]]; then fps="$fp"; else fps="${fps};${fp}"; fi
    case ";${seen_fps};" in
      *";${fp};"*) ;;
      *)
        seen_fps="${seen_fps};${fp}"
        uniq=$((uniq + 1))
        ;;
    esac
    echo "CANDIDATE kind=${kind} source=${src} fingerprint=${fp}"
  done <<< "$blob"
  echo "${label}_FOUND=${found}"
  echo "${label}_SOURCE=${srcs}"
  echo "${label}_FINGERPRINT=${fps}"
  echo "${label}_CANDIDATE_COUNT=$(echo "$blob" | grep -c . || echo 0)"
  if [[ "$uniq" -eq 1 ]]; then
    echo "${label}_UNIQUE=YES"
  else
    echo "${label}_UNIQUE=NO"
  fi
}

section "SUMMARY"
JWT_SECRET_KEY_FOUND=NO
VAULT_FERNET_KEY_FOUND=NO
ADMIN_TOKEN_FOUND=NO
JWT_UNIQUE=NO
VAULT_UNIQUE=NO
ADMIN_UNIQUE=NO

summarize_kind jwt "$JWT_CANDS" JWT_SECRET_KEY
summarize_kind vault "$VAULT_CANDS" VAULT_FERNET_KEY
summarize_kind admin "$ADMIN_CANDS" ADMIN_TOKEN

# Write restore plan ONLY when each required key has exactly one unique fingerprint.
# Plan stores sources + fingerprints (no secret values).
# Values file (chmod 600) holds unique candidates for restore only — never commit.
VALUES_FILE="${STATE_DIR}/secret-restore.values"
: > "${PLAN_FILE}"
: > "${VALUES_FILE}"
chmod 600 "${PLAN_FILE}" "${VALUES_FILE}" 2>/dev/null || true

pick_unique() {
  # argv blob: lines source|value  -> prints: SRC / FP / VALUE  or exit 1 if not unique
  # (do not use stdin — callers may pipe; heredoc would steal it)
  GUOQIAO_CAND_BLOB="$1" python3 - <<'PY'
import hashlib, os, sys
blob = os.environ.get("GUOQIAO_CAND_BLOB", "")
lines=[l for l in blob.splitlines() if l.strip() and "|" in l]
by_fp={}
for l in lines:
    src, val = l.split("|", 1)
    fp=hashlib.sha256(val.encode("utf-8")).hexdigest()[:12]
    by_fp.setdefault(fp, {"srcs": [], "val": val})
    if src not in by_fp[fp]["srcs"]:
        by_fp[fp]["srcs"].append(src)
if len(by_fp) != 1:
    sys.exit(1)
fp, meta = next(iter(by_fp.items()))
prefs=("envfile:", "state:", "launchagent:", "runtime_state:", "file:", "deploy:", "backup:", "stash:", "docker:", "git_hist", "log:", "compose:")
best=meta["srcs"][0]
for p in prefs:
    for s in meta["srcs"]:
        if s.startswith(p) or p.rstrip(":") in s:
            best=s
            break
    else:
        continue
    break
print(best)
print(fp)
print(meta["val"])
PY
}
JWT_SRC=""
VAULT_SRC=""
ADMIN_SRC=""
JWT_FP=""
VAULT_FP=""
ADMIN_FP=""

if [[ -n "$JWT_CANDS" ]]; then
  out="$(pick_unique "$JWT_CANDS" 2>/dev/null || true)"
  if [[ -n "$out" ]]; then
    JWT_SRC="$(printf '%s\n' "$out" | sed -n '1p')"
    JWT_FP="$(printf '%s\n' "$out" | sed -n '2p')"
    JWT_VAL="$(printf '%s\n' "$out" | sed -n '3p')"
    JWT_UNIQUE=YES
    JWT_SECRET_KEY_FOUND=YES
    printf 'JWT_SECRET_KEY=%s\n' "$JWT_VAL" >>"${VALUES_FILE}"
  else
    JWT_SECRET_KEY_FOUND=YES
    JWT_UNIQUE=NO
  fi
fi
if [[ -n "$VAULT_CANDS" ]]; then
  out="$(pick_unique "$VAULT_CANDS" 2>/dev/null || true)"
  if [[ -n "$out" ]]; then
    VAULT_SRC="$(printf '%s\n' "$out" | sed -n '1p')"
    VAULT_FP="$(printf '%s\n' "$out" | sed -n '2p')"
    VAULT_VAL="$(printf '%s\n' "$out" | sed -n '3p')"
    VAULT_UNIQUE=YES
    VAULT_FERNET_KEY_FOUND=YES
    printf 'VAULT_FERNET_KEY=%s\n' "$VAULT_VAL" >>"${VALUES_FILE}"
  else
    VAULT_FERNET_KEY_FOUND=YES
    VAULT_UNIQUE=NO
  fi
fi
if [[ -n "$ADMIN_CANDS" ]]; then
  out="$(pick_unique "$ADMIN_CANDS" 2>/dev/null || true)"
  if [[ -n "$out" ]]; then
    ADMIN_SRC="$(printf '%s\n' "$out" | sed -n '1p')"
    ADMIN_FP="$(printf '%s\n' "$out" | sed -n '2p')"
    ADMIN_VAL="$(printf '%s\n' "$out" | sed -n '3p')"
    ADMIN_UNIQUE=YES
    ADMIN_TOKEN_FOUND=YES
    printf 'ADMIN_TOKEN=%s\n' "$ADMIN_VAL" >>"${VALUES_FILE}"
  else
    ADMIN_TOKEN_FOUND=YES
    ADMIN_UNIQUE=NO
  fi
fi

{
  echo "# Generated by m1-runtime-secret-discover.sh — sources/fingerprints only"
  echo "JWT_UNIQUE=${JWT_UNIQUE}"
  echo "VAULT_UNIQUE=${VAULT_UNIQUE}"
  echo "ADMIN_UNIQUE=${ADMIN_UNIQUE}"
  echo "JWT_SOURCE=${JWT_SRC}"
  echo "VAULT_SOURCE=${VAULT_SRC}"
  echo "ADMIN_SOURCE=${ADMIN_SRC}"
  echo "JWT_FINGERPRINT=${JWT_FP}"
  echo "VAULT_FINGERPRINT=${VAULT_FP}"
  echo "ADMIN_FINGERPRINT=${ADMIN_FP}"
  echo "VALUES_FILE=${VALUES_FILE}"
} > "${PLAN_FILE}"
chmod 600 "${PLAN_FILE}" "${VALUES_FILE}"
# Never leave values world-readable
unset JWT_VAL VAULT_VAL ADMIN_VAL out 2>/dev/null || true

READY_RESTORE=NO
if [[ "$JWT_UNIQUE" == "YES" && "$VAULT_UNIQUE" == "YES" && "$ADMIN_UNIQUE" == "YES" ]]; then
  READY_RESTORE=YES
fi

echo "JWT_SECRET_KEY_FOUND=${JWT_SECRET_KEY_FOUND:-NO}"
echo "JWT_SECRET_SOURCE=${JWT_SRC}"
echo "JWT_SECRET_FINGERPRINT=${JWT_FP}"
echo "JWT_UNIQUE=${JWT_UNIQUE}"
echo "VAULT_FERNET_KEY_FOUND=${VAULT_FERNET_KEY_FOUND:-NO}"
echo "VAULT_SECRET_SOURCE=${VAULT_SRC}"
echo "VAULT_SECRET_FINGERPRINT=${VAULT_FP}"
echo "VAULT_UNIQUE=${VAULT_UNIQUE}"
echo "ADMIN_TOKEN_FOUND=${ADMIN_TOKEN_FOUND:-NO}"
echo "ADMIN_TOKEN_SOURCE=${ADMIN_SRC}"
echo "ADMIN_TOKEN_FINGERPRINT=${ADMIN_FP}"
echo "ADMIN_UNIQUE=${ADMIN_UNIQUE}"
echo "SECRET_RESTORE_PLAN=${PLAN_FILE}"
echo "SECRET_VALUES_FILE=${VALUES_FILE}"
echo "SECRET_OUTPUT_REDACTED=YES"
echo "SECRET_FINGERPRINT_ONLY=YES"
echo "READY_FOR_SECRET_RESTORE=${READY_RESTORE}"
if [[ "$READY_RESTORE" == "YES" ]]; then
  echo "SECRET_RECOVERY_COMPLETE=PENDING_RESTORE"
  echo "USER_ACTION_REQUIRED=NO"
  echo "NEXT_ACTION=bash deploy/api/m1-runtime-secret-restore.sh"
else
  echo "SECRET_RECOVERY_COMPLETE=NO"
  echo "USER_ACTION_REQUIRED=YES"
  echo "NEXT_ACTION=manual_provide_or_confirm_secret_candidates"
  echo "IMPACT_JWT=missing/ambiguous: old tokens/sessions may not continue; inventing a new JWT secret forces re-login — DO NOT auto-generate this round"
  echo "IMPACT_VAULT=missing/ambiguous: if historical customer_vaults/encrypted profile data exists, key must not be replaced casually; known counts may be 0 but DO NOT invent"
  echo "IMPACT_ADMIN=missing/ambiguous: admin token can be created later — DO NOT auto-generate this round"
fi
echo "DATABASE_REVISION_EXPECTED=006_student_profile_slots"
echo "DATABASE_CHANGED=NO"
echo "MIGRATION_RUN=NO"
echo "STASH_TOUCH=NO"
echo "============================================================"
echo "SECRET_DISCOVERY_COMPLETE"
echo "============================================================"
exit 0
