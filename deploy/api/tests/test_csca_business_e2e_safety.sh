#!/usr/bin/env bash
# Offline safety tests for m1-csca-v1-business-e2e.sh (no production DB).
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCR="${ROOT}/deploy/api/m1-csca-v1-business-e2e.sh"
REL="${ROOT}/deploy/api/m1-csca-v1-production-release.sh"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS+1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL+1)); }

[[ -f "$SCR" ]] || { echo "missing $SCR"; exit 1; }
bash -n "$SCR" && ok "bash_syntax" || ko "bash_syntax"

# Must align with production release binding
SCR_BACKEND="$(grep -E '^BACKEND=' "$SCR" | head -1)"
REL_BACKEND="$(grep -E '^BACKEND=' "$REL" | head -1)"
[[ "$SCR_BACKEND" == "$REL_BACKEND" ]] && ok "backend_path_aligned" || ko "backend_path_aligned ($SCR_BACKEND vs $REL_BACKEND)"

SCR_PG="$(grep -E '^PG_CONTAINER=' "$SCR" | head -1)"
REL_PG="$(grep -E '^PG_CONTAINER=' "$REL" | head -1)"
[[ "$SCR_PG" == "$REL_PG" ]] && ok "pg_container_aligned" || ko "pg_container_aligned"

grep -q 'EXPECTED_REV="009_csca_notification_rules"' "$SCR" && ok "expected_rev_009" || ko "expected_rev_009"
grep -q 'EXPECTED_AFTER="009_csca_notification_rules"' "$REL" && ok "release_rev_009" || ko "release_rev_009"

# Hard safety
grep -q 'SCHEDULER_ONESHOT_DEFAULT=NO' "$SCR" && ok "oneshot_default_no" || ko "oneshot_default_no"
grep -q 'SCHEDULER_ONESHOT=NOT_RUN' "$SCR" && ok "oneshot_not_run" || ko "oneshot_not_run"
grep -q 'FAKE_CSCA_DATE=NO' "$SCR" && ok "fake_date_no" || ko "fake_date_no"
grep -q 'SQL_TIMELINE_INSERT=NO' "$SCR" && ok "sql_insert_no" || ko "sql_insert_no"
grep -q 'BULK_COPY_900=NO' "$SCR" && ok "bulk_copy_no" || ko "bulk_copy_no"
grep -q 'MIGRATION=NO' "$SCR" && ok "migration_no" || ko "migration_no"
! grep -qE 'pg_restore|INSERT INTO student_timeline|oneshot=YES|dry_run=False' "$SCR" && ok "no_forbidden_ops" || ko "no_forbidden_ops"

# Modes
grep -q -- '--inspect-only' "$SCR" && ok "mode_inspect" || ko "mode_inspect"
grep -q -- '--sync-timeline' "$SCR" && ok "mode_sync" || ko "mode_sync"
grep -q -- '--apply-real-dates' "$SCR" && ok "mode_apply" || ko "mode_apply"
grep -q 'CONFIRM_CSCA_BUSINESS_WRITE' "$SCR" && ok "write_gate" || ko "write_gate"
grep -q 'CONFIRM_CSCA_TIMELINE_SYNC' "$SCR" && ok "sync_gate" || ko "sync_gate"

# Symbol alignment with live backend
CSCA="${ROOT}/huaqiao-saas-pro/backend/app/services/csca.py"
VAULT="${ROOT}/huaqiao-saas-pro/backend/app/services/vault_crypto.py"
SCHED="${ROOT}/huaqiao-saas-pro/backend/app/services/notifications/scheduler.py"
grep -q 'def sync_csca_timeline' "$CSCA" && grep -q 'sync_csca_timeline' "$SCR" && ok "sync_symbol" || ko "sync_symbol"
grep -q 'def parse_real_date' "$CSCA" && grep -q 'parse_real_date' "$SCR" && ok "parse_symbol" || ko "parse_symbol"
grep -q 'def decrypt_profile_json' "$VAULT" && grep -q 'decrypt_profile_json' "$SCR" && ok "decrypt_symbol" || ko "decrypt_symbol"
grep -q 'def run_scheduler_tick' "$SCHED" && grep -q 'run_scheduler_tick' "$SCR" && ok "scheduler_symbol" || ko "scheduler_symbol"

# Report banner
grep -q 'GUOQIAO_CSCA_FINAL_E2E_REPORT' "$SCR" && ok "report_banner" || ko "report_banner"
for k in DB_REVISION TEST_STUDENT_ID CSCA_STATUS CSCA_DATE_SOURCE STUDENT_TIMELINE_ITEM_COUNT \
  CSCA_TIMELINE_CREATED CSCA_TIMELINE_DEDUPE REMINDER_DRY_RUN CANDIDATE_COUNT WOULD_CREATE_COUNT \
  DEDUPE_SKIPPED_COUNT CANDIDATES_VALID READY_FOR_ONESHOT SCHEDULER_ONESHOT SECOND_RUN_DUPLICATE_CREATED \
  ADMIN_360_CSCA STUDENT_H5_CSCA CSCA_NOTIFICATION_E2E PRODUCTION_FREEZE NEXT_ACTION; do
  grep -q "\"$k\"" "$SCR" && ok "report_key_$k" || ko "report_key_$k"
done

echo "SUMMARY pass=$N_PASS fail=$N_FAIL"
[[ "$N_FAIL" -eq 0 ]]
