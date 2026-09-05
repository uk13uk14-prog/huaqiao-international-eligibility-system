#!/usr/bin/env bash
# Unit tests: Student CRM 010 release state machine (no production DB).
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCR="${ROOT}/deploy/api/m1-student-crm-v2-production-release.sh"
LIB="${ROOT}/deploy/api/lib/student_crm_010_schema_guard.sh"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

[[ -f "$SCR" ]] || { echo "missing $SCR"; exit 1; }
[[ -f "$LIB" ]] || { echo "missing $LIB"; exit 1; }

# shellcheck source=deploy/api/lib/student_crm_010_schema_guard.sh
source "$LIB"

EXPECTED_BEFORE="009_csca_notification_rules"
EXPECTED_AFTER="010_student_crm_v1"
EXPECTED_POST_NOTIFICATION_RULES=51
EXPECTED_CSCA_RULES=24
EXPECTED_NON_CSCA_RULES=27

YES4=(YES YES YES YES)
NO10=(NO NO NO NO NO NO NO NO NO NO)
YES10=(YES YES YES YES YES YES YES YES YES YES)

# CASE1: rev=009, notif 4/4, rules 51/24/27, 010 objects 0 => A_CLEAN_PRE_010
classify_010_release_state \
  "$EXPECTED_BEFORE" \
  "${YES4[@]}" \
  51 24 27 \
  "${NO10[@]}" >/dev/null
[[ "$SCHEMA_STATE_010" == "A_CLEAN_PRE_010" && "$CLEAN_PRE_010" == "YES" && "$ALLOW_010_UPGRADE" == "YES" ]] \
  && ok "CASE1_CLEAN_PRE_010" || ko "CASE1_CLEAN_PRE_010 ($SCHEMA_STATE_010 allow=$ALLOW_010_UPGRADE)"

# CASE2: rev=009, partial 010 objects => C_PARTIAL_010
partial=("${NO10[@]}")
partial[0]=YES  # follow_ups only
classify_010_release_state \
  "$EXPECTED_BEFORE" \
  "${YES4[@]}" \
  51 24 27 \
  "${partial[@]}" >/dev/null
[[ "$SCHEMA_STATE_010" == "C_PARTIAL_010" && "$PARTIAL_010" == "YES" && "$ALLOW_010_UPGRADE" == "NO" ]] \
  && ok "CASE2_PARTIAL_010" || ko "CASE2_PARTIAL_010 ($SCHEMA_STATE_010)"

# CASE3: rev=010, all objects, rules correct => B_ALREADY_010
classify_010_release_state \
  "$EXPECTED_AFTER" \
  "${YES4[@]}" \
  51 24 27 \
  "${YES10[@]}" >/dev/null
[[ "$SCHEMA_STATE_010" == "B_ALREADY_010" && "$ALREADY_UPGRADED_010" == "YES" && "$SKIP_010_MIGRATE" == "YES" && "$ALLOW_010_UPGRADE" == "NO" ]] \
  && ok "CASE3_ALREADY_010" || ko "CASE3_ALREADY_010 ($SCHEMA_STATE_010)"

# CASE4: rev=010, missing CRM column => C_PARTIAL_010
incomplete=("${YES10[@]}")
incomplete[4]=NO  # missing crm_stage
classify_010_release_state \
  "$EXPECTED_AFTER" \
  "${YES4[@]}" \
  51 24 27 \
  "${incomplete[@]}" >/dev/null
[[ "$SCHEMA_STATE_010" == "C_PARTIAL_010" && "$PARTIAL_010" == "YES" && "$ALLOW_010_UPGRADE" == "NO" ]] \
  && ok "CASE4_INCOMPLETE_010" || ko "CASE4_INCOMPLETE_010 ($SCHEMA_STATE_010)"

# CASE5: rules != 51 => D_INCONSISTENT_010
classify_010_release_state \
  "$EXPECTED_BEFORE" \
  "${YES4[@]}" \
  50 24 26 \
  "${NO10[@]}" >/dev/null
[[ "$SCHEMA_STATE_010" == "D_INCONSISTENT_010" && "$INCONSISTENT_010" == "YES" && "$ALLOW_010_UPGRADE" == "NO" ]] \
  && ok "CASE5_RULE_MISMATCH" || ko "CASE5_RULE_MISMATCH ($SCHEMA_STATE_010)"

# CASE6: unexpected revision => D_INCONSISTENT_010
classify_010_release_state \
  "008_notification_center_v1" \
  "${YES4[@]}" \
  51 24 27 \
  "${NO10[@]}" >/dev/null
[[ "$SCHEMA_STATE_010" == "D_INCONSISTENT_010" && "$INCONSISTENT_010" == "YES" && "$ALLOW_010_UPGRADE" == "NO" ]] \
  && ok "CASE6_UNEXPECTED_REVISION" || ko "CASE6_UNEXPECTED_REVISION ($SCHEMA_STATE_010)"

# Wiring assertions
grep -q 'classify_010_release_state\|evaluate_010_release_gate' "$SCR" && ok "010_GATE_WIRED" || ko "010_GATE_WIRED"
grep -q 'ALLOW_010_UPGRADE' "$SCR" && ok "ALLOW_010_UPGRADE_PRESENT" || ko "ALLOW_010_UPGRADE_PRESENT"
grep -q 'SCHEMA_STATE_010' "$SCR" && ok "SCHEMA_STATE_010_PRESENT" || ko "SCHEMA_STATE_010_PRESENT"
grep -q 'OLD_009_GATE_NOT_USED_FOR_010_APPLY=YES\|OLD_009_APPLY_GATES_NOT_USED_FOR_010=YES' "$SCR" \
  && ok "OLD_009_BYPASS_FLAG" || ko "OLD_009_BYPASS_FLAG"
grep -q 'A_CLEAN_PRE_010' "$SCR" && ok "DIAGNOSTIC_REQUIRES_A_CLEAN_PRE_010" || ko "DIAGNOSTIC_REQUIRES_A_CLEAN_PRE_010"
grep -q 'B_ALREADY_010' "$SCR" && ok "POST_REQUIRES_B_ALREADY_010" || ko "POST_REQUIRES_B_ALREADY_010"

# Ensure apply path requires ALLOW_010_UPGRADE and does not refuse on ALLOW_009_UPGRADE
non="$(mktemp)"
grep -vE '^[[:space:]]*#' "$SCR" >"$non" || true
if grep -nE 'refuse upgrade: ALLOW_009_UPGRADE|refuse upgrade: CLEAN_PRE_009|refuse upgrade: ALLOW_008_UPGRADE' "$non"; then
  ko "OLD_008_009_APPLY_GATE_REMOVED"
else
  ok "OLD_008_009_APPLY_GATE_REMOVED"
fi
if awk '
  /CHECKPOINT D — APPLY 010|CHECKPOINT D — APPLY 010/ {in_apply=1}
  in_apply && /ALLOW_010_UPGRADE/ {seen010=1}
  in_apply && /refuse upgrade: ALLOW_009_UPGRADE/ {bad=1}
  in_apply && /^section |^########/ && !/APPLY 010/ {in_apply=0}
  END { if (bad) exit 2; if (!seen010) exit 3; exit 0 }
' "$SCR"; then
  ok "APPLY_USES_ALLOW_010_NOT_009"
else
  ko "APPLY_USES_ALLOW_010_NOT_009"
fi
rm -f "$non"

bash -n "$SCR" && ok "BASH_SYNTAX_RELEASE_SCRIPT" || ko "BASH_SYNTAX_RELEASE_SCRIPT"
bash -n "$LIB" && ok "BASH_SYNTAX_010_GUARD_LIB" || ko "BASH_SYNTAX_010_GUARD_LIB"

echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
