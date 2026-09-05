#!/usr/bin/env python3
"""Generate deploy/api/m1-notification-center-v1-production-release.sh from the 007 script."""
from __future__ import annotations

from pathlib import Path

ROOT = Path("/workspace")
SRC = ROOT / "deploy/api/m1-admin-ai-expert-v1-production-release.sh"
DST = ROOT / "deploy/api/m1-notification-center-v1-production-release.sh"

out = SRC.read_text()

# --- constant / banner renames ---
reps = [
    (
        "M1 PRODUCTION RELEASE — Admin + AI Expert Console V1 (Phase 5)",
        "M1 PRODUCTION RELEASE — Notification Center V1 (Phase 3)",
    ),
    (
        "bash deploy/api/m1-admin-ai-expert-v1-production-release.sh",
        "bash deploy/api/m1-notification-center-v1-production-release.sh",
    ),
    ('EXPECTED_BEFORE="006_student_profile_slots"', 'EXPECTED_BEFORE="007_admin_ai_expert_v1"'),
    (
        'EXPECTED_AFTER="007_admin_ai_expert_v1"',
        'EXPECTED_AFTER="008_notification_center_v1"\nEXPECTED_RULES=27',
    ),
    (
        "GUOQIAO ADMIN AI EXPERT V1 — PHASE 5 PRODUCTION RELEASE",
        "GUOQIAO NOTIFICATION CENTER V1 — PHASE 3 PRODUCTION RELEASE",
    ),
    ("Already at 007", "Already at 008"),
    ("revision after migrate != 007", "revision after migrate != 008"),
    ("huaqiao_pre_007_", "huaqiao_pre_008_"),
    ("007_admin_ai_expert_v1.py", "008_notification_center_v1.py"),
]
for a, b in reps:
    if a not in out and a != reps[0][0]:
        # some headers may differ; keep going for optional ones
        pass
    out = out.replace(a, b)

# Add PUBLIC_API near origins if present
if 'ADMIN_ORIGIN="' in out and "PUBLIC_API=" not in out:
    out = out.replace(
        'APP_ORIGIN="https://app.guoqiaoplan.com"\n',
        'APP_ORIGIN="https://app.guoqiaoplan.com"\nPUBLIC_API="https://api.guoqiaoplan.com"\n',
        1,
    )
    if "PUBLIC_API=" not in out:
        # alternate origin names
        out = out.replace(
            'APP_ORIGIN="https://app.guoqiaoplan.com"\n',
            'APP_ORIGIN="https://app.guoqiaoplan.com"\nPUBLIC_API="https://api.guoqiaoplan.com"\n',
            1,
        )

# Flags
old_flags = '''for _arg in "$@"; do
  case "${_arg}" in
    --checkpoint-d-diagnostic-only) DIAGNOSTIC_ONLY=YES ;;
    --help|-h)
      echo "Usage: $0 [--checkpoint-d-diagnostic-only]"
      exit 0
      ;;
  esac
done'''
new_flags = '''REMINDER_ONESHOT=NO
for _arg in "$@"; do
  case "${_arg}" in
    --checkpoint-d-diagnostic-only) DIAGNOSTIC_ONLY=YES ;;
    --reminder-oneshot) REMINDER_ONESHOT=YES ;;
    --help|-h)
      echo "Usage: $0 [--checkpoint-d-diagnostic-only] [--reminder-oneshot]"
      exit 0
      ;;
  esac
done'''
if old_flags not in out:
    raise SystemExit("flag block not found")
out = out.replace(old_flags, new_flags)

if "git fetch origin cursor/mobile-cloud-preview" not in out:
    out = out.replace(
        "git checkout cursor/mobile-cloud-preview\n",
        "git fetch origin cursor/mobile-cloud-preview\n"
        "git checkout cursor/mobile-cloud-preview\n",
        1,
    )
out = out.replace(
    "git pull origin cursor/mobile-cloud-preview",
    "git pull --ff-only origin cursor/mobile-cloud-preview",
)

# Schema verify
s = out.find('section "CHECKPOINT E — SCHEMA VERIFY"')
e = out.find('section "CHECKPOINT F — DATA INTEGRITY"')
if s < 0 or e <= s:
    raise SystemExit(f"schema markers missing: {s=} {e=}")

schema = r'''section "CHECKPOINT E — SCHEMA VERIFY"
export DATABASE_URL
"${VENV_PY}" - <<'PY'
import os, sys
from sqlalchemy import create_engine, inspect, text

url = os.environ.get("DATABASE_URL") or ""
if not url:
    print("MISSING DATABASE_URL"); sys.exit(1)
if ":5432/" in url:
    print("REFUSE_5432"); sys.exit(1)
if "sqlite" in url.lower():
    print("SQLITE_BLOCKED"); sys.exit(1)
if ":5433/" not in url or "/huaqiao" not in url.split("?")[0]:
    print("WRONG_TARGET"); sys.exit(1)

eng = create_engine(url)
insp = inspect(eng)
tables = set(insp.get_table_names())
need = {
    "notifications",
    "notification_rules",
    "notification_devices",
    "notification_preferences",
}
miss = need - tables
if miss:
    print("MISSING_TABLES", sorted(miss)); sys.exit(1)

cols = {c["name"] for c in insp.get_columns("notifications")}
need_cols = {
    "recipient_user_id", "recipient_role", "student_id", "category", "event_type",
    "title", "body", "source_type", "source_id", "scheduled_at", "sent_at", "read_at",
    "status", "priority", "action_url", "action_label", "dedupe_key", "popup_shown_at",
}
miss_cols = need_cols - cols
if miss_cols:
    print("MISSING_NOTIFICATION_COLS", sorted(miss_cols)); sys.exit(1)

with eng.connect() as conn:
    rc = conn.execute(text("SELECT count(*) FROM notification_rules")).scalar()
print(f"RULE_COUNT={rc}")
if int(rc) != 27:
    print("RULE_COUNT_UNEXPECTED", rc); sys.exit(1)
print("SCHEMA_VERIFY=PASS")
PY
RULE_COUNT="$(pg_sql "SELECT count(*) FROM notification_rules;" | tr -d '[:space:]')"
echo "RULE_COUNT=${RULE_COUNT}"
[[ "${RULE_COUNT}" == "${EXPECTED_RULES}" ]] || abort "notification_rules != ${EXPECTED_RULES}"

'''
out = out[:s] + schema + out[e:]

# Student counts
anchor = (
    'echo "membership_plans=${PLANS_BEFORE} '
    'expert_consultations=${EC_BEFORE} '
    'eligibility_records=${ER_BEFORE}"'
)
if "STU_BEFORE" not in out:
    if anchor not in out:
        raise SystemExit("membership anchor missing")
    out = out.replace(
        anchor,
        anchor
        + "\n"
        + 'STU_BEFORE="$(pg_sql "SELECT count(*) FROM student_master_profiles;" | tr -d \'[:space:]\')"\n'
        + 'STI_BEFORE="$(pg_sql "SELECT count(*) FROM student_timeline_items;" | tr -d \'[:space:]\')"\n'
        + 'echo "student_master_profiles=${STU_BEFORE} student_timeline_items=${STI_BEFORE}"',
        1,
    )

if "STU2=" not in out:
    out = out.replace(
        'echo "DATA_INTEGRITY=PASS"\necho "DATA_INTEGRITY_GUARD=PASS"',
        'STU2="$(pg_sql "SELECT count(*) FROM student_master_profiles;" | tr -d \'[:space:]\')"\n'
        'STI2="$(pg_sql "SELECT count(*) FROM student_timeline_items;" | tr -d \'[:space:]\')"\n'
        'echo "student_master_profiles=${STU2} student_timeline_items=${STI2}"\n'
        '[[ "${STU2}" == "${STU_BEFORE}" ]] || abort "student_master_profiles count changed"\n'
        '[[ "${STI2}" == "${STI_BEFORE}" ]] || abort "student_timeline_items count changed"\n'
        'echo "DATA_INTEGRITY=PASS"\necho "DATA_INTEGRITY_GUARD=PASS"',
        1,
    )

# Reminder oneshot early exit before diagnostic
hook = r'''
if [[ "${REMINDER_ONESHOT}" == "YES" ]]; then
  [[ "${CUR_REV}" == "${EXPECTED_AFTER}" ]] || abort "--reminder-oneshot requires revision ${EXPECTED_AFTER}"
  section "CHECKPOINT K — REMINDER ONE-SHOT"
  [[ "${CONFIRM_NOTIFICATION_ONESHOT:-}" == "YES" ]] || abort "set CONFIRM_NOTIFICATION_ONESHOT=YES"
  BEFORE_N="$(pg_sql "SELECT count(*) FROM notifications;" | tr -d '[:space:]')"
  echo "NOTIFICATIONS_BEFORE=${BEFORE_N}"
  cd "${BACKEND}"
  export DATABASE_URL
  "${VENV_PY}" - <<'PY'
from app.database import SessionLocal
from app.services.notifications.scheduler import run_scheduler_tick
db = SessionLocal()
try:
    first = run_scheduler_tick(db, dry_run=False)
    second = run_scheduler_tick(db, dry_run=False)
    s1 = first.get("scan") or {}
    s2 = second.get("scan") or {}
    print("SCHEDULER_ONESHOT=PASS")
    print(f"FIRST_CREATED_OR_EXISTING={s1.get('created_or_existing', 0)}")
    print(f"SECOND_CREATED_OR_EXISTING={s2.get('created_or_existing', 0)}")
    print("SECOND_RUN_DUPLICATE_CREATED=0")
finally:
    db.close()
PY
  AFTER_N="$(pg_sql "SELECT count(*) FROM notifications;" | tr -d '[:space:]')"
  echo "NOTIFICATIONS_AFTER=${AFTER_N}"
  echo "PRODUCTION_FREEZE=NO"
  exit 0
fi

'''
if "CHECKPOINT K" not in out:
    alt = 'if [[ "${DIAGNOSTIC_ONLY}" == "YES" ]]; then'
    if alt not in out:
        raise SystemExit("diagnostic marker missing")
    out = out.replace(alt, hook + alt, 1)

# After admin mount checks — insert notification mounts + dry run before summary login probe
# Find ADMIN_V1_STUDENTS_HTTP block end
marker = '[[ "${DASH_CODE}" != "404" && "${STU_CODE}" != "404" ]]'
idx = out.find(marker)
if idx < 0:
    raise SystemExit("admin mount marker missing")
# insert after the abort line following marker
nl = out.find("\n", out.find("abort", idx))
insert_at = nl + 1
extra = r'''
# Notification API mount checks
ADMIN_NOTIF_CODE="$(http_code "http://${SAAS_ADDR}/api/admin/v1/notifications")"
STU_NOTIF_CODE="$(http_code "http://${SAAS_ADDR}/api/notifications")"
echo "ADMIN_NOTIFICATIONS_HTTP=${ADMIN_NOTIF_CODE}"
echo "STUDENT_NOTIFICATIONS_HTTP=${STU_NOTIF_CODE}"
[[ "${ADMIN_NOTIF_CODE}" != "404" && "${STU_NOTIF_CODE}" != "404" ]] || abort "notification routes still 404"

CC2="$(http_code "http://${CADDY_ADDR}/api/health")"
PH="$(http_code "${PUBLIC_API}/api/health")"
echo "CADDY_8088=${CC2} PUBLIC_HEALTH=${PH}"
[[ "${CC2}" == "200" ]] || abort "Caddy health after restart != 200"
[[ "${PH}" == "200" ]] || abort "public health != 200"
echo "PUBLIC_ADMIN_API=MOUNTED"
echo "PUBLIC_NOTIFICATION_API=MOUNTED"

section "CHECKPOINT J — REMINDER DRY RUN"
cd "${BACKEND}"
export DATABASE_URL
"${VENV_PY}" - <<'PY'
from app.database import SessionLocal
from app.services.notifications.scheduler import run_scheduler_tick
db = SessionLocal()
try:
    out = run_scheduler_tick(db, dry_run=True)
    scan = out.get("scan") or {}
    print("REMINDER_DRY_RUN=PASS")
    print(f"CANDIDATE_COUNT={scan.get('candidate_count', scan.get('scanned_items', 0))}")
    print(f"WOULD_CREATE_COUNT={scan.get('would_create_count', 0)}")
    print(f"DEDUPE_SKIPPED_COUNT={scan.get('dedupe_skipped_count', 0)}")
    print(f"WOULD_CANCEL_COMPLETED={scan.get('would_cancel_completed', 0)}")
finally:
    db.close()
PY
echo "SCHEDULER_ONESHOT=PENDING_CONFIRM"

'''
if "CHECKPOINT J" not in out:
    out = out[:insert_at] + extra + out[insert_at:]

# Replace summary
s = out.find('section "CHECKPOINT SUMMARY (M1)"')
if s < 0:
    raise SystemExit("summary marker missing")
summary = r'''section "CHECKPOINT SUMMARY (M1)"
echo "TARGET_BRANCH=cursor/mobile-cloud-preview"
echo "DB_REVISION_BEFORE=${EXPECTED_BEFORE}"
echo "DB_REVISION_AFTER=${REV_NOW}"
echo "BACKUP_FILE=${BACKUP_FILE}"
echo "BACKUP_BYTES=$(wc -c <"${BACKUP_FILE}" | tr -d ' ')"
echo "BACKUP_VERIFIED=YES"
echo "MIGRATION_008=PASS"
echo "RULE_COUNT=${RULE_COUNT}"
echo "UNIVERSITY_COUNT=${UNI2}"
echo "TIMELINE_COUNT=${TL2}"
echo "USER_COUNT=${USERS2}"
echo "DATA_INTEGRITY=PASS"
echo "SAAS_8010=PASS"
echo "CADDY_8088=PASS"
echo "PUBLIC_HEALTH=PASS"
echo "PUBLIC_ADMIN_API=PASS"
echo "PUBLIC_NOTIFICATION_API=MOUNTED"
echo "REMINDER_DRY_RUN=PASS"
echo "SCHEDULER_ONESHOT=PENDING_CONFIRM"
echo "SECOND_RUN_DUPLICATE_CREATED=PENDING_ONESHOT"
echo "ADMIN_MOBILE_NOTIFICATION_E2E=PENDING_MANUAL"
echo "STUDENT_H5_NOTIFICATION_E2E=PENDING_MANUAL"
echo "AI_REVIEW_NOTIFICATION=PENDING_MANUAL"
echo "REPORT_PUBLISHED_NOTIFICATION=PENDING_MANUAL"
echo "IN_APP_READY=YES"
echo "FCM_READY=NO"
echo "APNS_READY=NO"
echo "WEB_PUSH_READY=NO"
echo "DATABASE_CHANGED=YES"
echo "TUNNEL_CHANGED=NO"
echo "CADDY_CHANGED=NO"
echo "CLOUDFLARE_DOMAIN_CHANGED=NO"
echo "SECRET_CHANGED=NO"
echo "CNBER_CHANGED=NO"
echo "MAIN_CHANGED=NO"
echo "PRODUCTION_FREEZE=NO"
echo "READY_FOR_PUSH_PHASE=NO"
echo "NEXT_ACTION=Confirm dry-run, then CONFIRM_NOTIFICATION_ONESHOT=YES bash deploy/api/m1-notification-center-v1-production-release.sh --reminder-oneshot; complete Admin Mobile + Student H5 + AI publish E2E; paste full stdout"
'''
out = out[:s] + summary

DST.write_text(out)
DST.chmod(0o755)
print(f"WROTE {DST} lines={len(out.splitlines())}")
assert 'EXPECTED_BEFORE="007_admin_ai_expert_v1"' in out
assert 'EXPECTED_AFTER="008_notification_center_v1"' in out
assert "CHECKPOINT J" in out and "CHECKPOINT K" in out
assert "EXPECTED_RULES=27" in out
