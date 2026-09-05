#!/usr/bin/env bash
# Unit tests: Admin Console 011 release state machine (no production DB).
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LIB="${ROOT}/deploy/api/lib/admin_console_011_schema_guard.sh"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

[[ -f "$LIB" ]] || { echo "missing $LIB"; exit 1; }
# shellcheck source=deploy/api/lib/admin_console_011_schema_guard.sh
source "$LIB"

EXPECTED_BEFORE="010_student_crm_v1"
EXPECTED_AFTER="011_admin_console_v2"
EXPECTED_POST_NOTIFICATION_RULES=51
EXPECTED_CSCA_RULES=24
EXPECTED_NON_CSCA_RULES=27

NO5=(NO NO NO NO NO)
YES5=(YES YES YES YES YES)

classify_011_release_state "$EXPECTED_BEFORE" 51 24 27 "${NO5[@]}" >/dev/null
[[ "$SCHEMA_STATE_011" == "A_CLEAN_PRE_011" && "$ALLOW_011_UPGRADE" == "YES" ]] \
  && ok "CASE1_CLEAN_PRE_011" || ko "CASE1_CLEAN_PRE_011 ($SCHEMA_STATE_011)"

classify_011_release_state "$EXPECTED_AFTER" 51 24 27 "${YES5[@]}" >/dev/null
[[ "$SCHEMA_STATE_011" == "B_ALREADY_011" && "$SKIP_011_MIGRATE" == "YES" ]] \
  && ok "CASE2_ALREADY_011" || ko "CASE2_ALREADY_011 ($SCHEMA_STATE_011)"

partial=("${NO5[@]}")
partial[0]=YES
classify_011_release_state "$EXPECTED_BEFORE" 51 24 27 "${partial[@]}" >/dev/null
[[ "$SCHEMA_STATE_011" == "C_PARTIAL_011" && "$ALLOW_011_UPGRADE" == "NO" ]] \
  && ok "CASE3_PARTIAL_011" || ko "CASE3_PARTIAL_011 ($SCHEMA_STATE_011)"

classify_011_release_state "$EXPECTED_BEFORE" 50 24 26 "${NO5[@]}" >/dev/null
[[ "$SCHEMA_STATE_011" == "D_INCONSISTENT_011" && "$ALLOW_011_UPGRADE" == "NO" ]] \
  && ok "CASE4_RULE_MISMATCH" || ko "CASE4_RULE_MISMATCH ($SCHEMA_STATE_011)"

classify_011_release_state "009_csca_notification_rules" 51 24 27 "${NO5[@]}" >/dev/null
[[ "$SCHEMA_STATE_011" == "D_INCONSISTENT_011" ]] \
  && ok "CASE5_WRONG_REV" || ko "CASE5_WRONG_REV ($SCHEMA_STATE_011)"

# Independence: stale 008/009/010 apply flags must not decide 011.
ALLOW_008_UPGRADE=NO
ALLOW_009_UPGRADE=NO
ALLOW_010_UPGRADE=NO
CLEAN_PRE_010=NO
PARTIAL_010=YES
INCONSISTENT_010=YES
classify_011_release_state "$EXPECTED_BEFORE" 51 24 27 "${NO5[@]}" >/dev/null
[[ "$SCHEMA_STATE_011" == "A_CLEAN_PRE_011" && "$ALLOW_011_UPGRADE" == "YES" ]] \
  && ok "CASE5B_INDEPENDENT_OF_OLD_GATES" || ko "CASE5B_INDEPENDENT_OF_OLD_GATES ($SCHEMA_STATE_011 allow=$ALLOW_011_UPGRADE)"

validate_011_account_kind_integrity 10 3 10 3 7 0 >/dev/null \
  && ok "CASE6_KIND_OK" || ko "CASE6_KIND_OK"
validate_011_account_kind_integrity 10 3 10 4 6 1 >/dev/null \
  && ko "CASE7_KIND_FLIP_SHOULD_FAIL" || ok "CASE7_KIND_FLIP_BLOCKED"

SCR="${ROOT}/deploy/api/m1-admin-console-v2-production-release.sh"
if [[ -f "$SCR" ]]; then
  grep -q '127.0.0.1' "$SCR" && grep -q '5433' "$SCR" && grep -q 'NO auto pg_restore\|AUTO_PG_RESTORE=NO\|Do NOT auto pg_restore' "$SCR" \
    && ok "SCRIPT_SAFETY_STRINGS" || ko "SCRIPT_SAFETY_STRINGS"
  grep -qE ':5432/' "$SCR" && grep -q 'refuse\|BLOCKED\|abort' "$SCR" \
    && ok "SCRIPT_REFUSES_5432" || ko "SCRIPT_REFUSES_5432"
else
  ko "missing production release script"
fi

echo "PASS=${N_PASS} FAIL=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
