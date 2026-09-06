#!/usr/bin/env bash
# Unit tests: CSCA 009 release state machine (independent of 008 upgrade gates).
# No production DB access.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCR="${ROOT}/deploy/api/m1-csca-v1-production-release.sh"
LIB="${ROOT}/deploy/api/lib/csca_009_integrity_guard.sh"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

[[ -f "$SCR" ]] || { echo "missing $SCR"; exit 1; }
[[ -f "$LIB" ]] || { echo "missing $LIB"; exit 1; }

# shellcheck source=deploy/api/lib/csca_009_integrity_guard.sh
source "$LIB"

EXPECTED_BEFORE="008_notification_center_v1"
EXPECTED_AFTER="009_csca_notification_rules"
EXPECTED_UNI=125
EXPECTED_TL=900
EXPECTED_PRE_NOTIFICATION_RULES=27
EXPECTED_CSCA_RULES=24
EXPECTED_POST_NOTIFICATION_RULES=51
EXPECTED_NON_CSCA_RULES=27

# --- A) CLEAN_PRE_009 ---
classify_009_release_state "$EXPECTED_BEFORE" 0 27 27 >/dev/null
[[ "$SCHEMA_STATE_009" == "A_CLEAN_PRE_009" && "$CLEAN_PRE_009" == "YES" && "$ALLOW_009_UPGRADE" == "YES" ]] \
  && ok "STATE_A_CLEAN_PRE_009" || ko "STATE_A_CLEAN_PRE_009 ($SCHEMA_STATE_009)"

# --- B) PARTIAL_009 ---
classify_009_release_state "$EXPECTED_BEFORE" 12 27 39 >/dev/null
[[ "$SCHEMA_STATE_009" == "B_PARTIAL_009" && "$PARTIAL_009" == "YES" && "$ALLOW_009_UPGRADE" == "NO" ]] \
  && ok "STATE_B_PARTIAL_009" || ko "STATE_B_PARTIAL_009 ($SCHEMA_STATE_009)"

# --- C) ALREADY_UPGRADED_009 ---
classify_009_release_state "$EXPECTED_AFTER" 24 27 51 >/dev/null
[[ "$SCHEMA_STATE_009" == "C_ALREADY_009" && "$ALREADY_UPGRADED_009" == "YES" && "$SKIP_009_MIGRATE" == "YES" && "$ALLOW_009_UPGRADE" == "NO" ]] \
  && ok "STATE_C_ALREADY_009" || ko "STATE_C_ALREADY_009 ($SCHEMA_STATE_009)"

# --- D) INCONSISTENT_009 ---
classify_009_release_state "$EXPECTED_AFTER" 20 27 47 >/dev/null
[[ "$SCHEMA_STATE_009" == "D_INCONSISTENT_009" && "$INCONSISTENT_009" == "YES" && "$ALLOW_009_UPGRADE" == "NO" ]] \
  && ok "STATE_D_INCONSISTENT_009" || ko "STATE_D_INCONSISTENT_009 ($SCHEMA_STATE_009)"

# 008 already upgraded is valid base for 009
evaluate_base_008_schema_ready "C_ALREADY_008" 4 "$EXPECTED_BEFORE" >/dev/null
[[ "$BASE_008_SCHEMA_READY" == "YES" ]] \
  && ok "008_ALREADY_UPGRADED_IS_VALID_BASE_FOR_009" || ko "008_ALREADY_UPGRADED_IS_VALID_BASE_FOR_009"

# Partial 008 must NOT be ready base
evaluate_base_008_schema_ready "B_PARTIAL_008" 2 "$EXPECTED_BEFORE" >/dev/null || true
[[ "$BASE_008_SCHEMA_READY" == "NO" ]] \
  && ok "008_PARTIAL_NOT_VALID_BASE" || ko "008_PARTIAL_NOT_VALID_BASE"

# Dynamic users still enforced
validate_post_integrity 8 8 125 125 900 900 51 24 27 >/dev/null \
  && ok "PRE_USERS_8_POST_8_PASS" || ko "PRE_USERS_8_POST_8_PASS"
validate_post_integrity 800 800 125 125 900 900 51 24 27 >/dev/null \
  && ok "PRE_USERS_800_POST_800_PASS" || ko "PRE_USERS_800_POST_800_PASS"
if validate_post_integrity 8 7 125 125 900 900 51 24 27 >/dev/null; then
  ko "USER_LOSS_FAIL_CLOSED"
else
  ok "USER_LOSS_FAIL_CLOSED"
fi

# Rule transitions
validate_pre_fingerprint 125 900 8 27 >/dev/null && ok "PRE_RULES_27_OK" || ko "PRE_RULES_27_OK"
validate_post_integrity 8 8 125 125 900 900 51 24 27 >/dev/null && ok "RULES_27_TO_51_OK" || ko "RULES_27_TO_51_OK"
if validate_post_integrity 8 8 125 125 900 900 51 23 28 >/dev/null; then
  ko "CSCA_24_ENFORCED"
else
  ok "CSCA_24_ENFORCED"
fi
if validate_post_integrity 8 8 125 125 900 900 51 24 26 >/dev/null; then
  ko "NON_CSCA_27_ENFORCED"
else
  ok "NON_CSCA_27_ENFORCED"
fi

# Static script assertions: old 008 apply gates must not block 009
non="$(mktemp)"
grep -vE '^[[:space:]]*#' "$SCR" >"$non" || true

if grep -nE 'refuse upgrade: ALLOW_008_UPGRADE|refuse upgrade: CLEAN_PRE_008' "$non"; then
  ko "OLD_008_APPLY_GATE_REMOVED"
else
  ok "OLD_008_APPLY_GATE_REMOVED"
fi

grep -q 'ALLOW_009_UPGRADE' "$SCR" && ok "ALLOW_009_UPGRADE_PRESENT" || ko "ALLOW_009_UPGRADE_PRESENT"
grep -q 'CLEAN_PRE_009' "$SCR" && ok "CLEAN_PRE_009_PRESENT" || ko "CLEAN_PRE_009_PRESENT"
grep -q 'BASE_008_SCHEMA_READY' "$SCR" && ok "BASE_008_SCHEMA_READY_PRESENT" || ko "BASE_008_SCHEMA_READY_PRESENT"
grep -q 'classify_009_release_state' "$SCR" && ok "classify_009_WIRED" || ko "classify_009_WIRED"
grep -q 'OLD_008_GATE_NOT_USED_FOR_009_APPLY=YES' "$SCR" && ok "OLD_008_GATE_BYPASS_FLAG" || ko "OLD_008_GATE_BYPASS_FLAG"
grep -q 'CSCA_RULE_COUNT_BEFORE' "$SCR" && ok "CSCA_RULE_COUNT_BEFORE_PRESENT" || ko "CSCA_RULE_COUNT_BEFORE_PRESENT"
grep -q 'NON_CSCA_RULE_COUNT_BEFORE' "$SCR" && ok "NON_CSCA_RULE_COUNT_BEFORE_PRESENT" || ko "NON_CSCA_RULE_COUNT_BEFORE_PRESENT"

# Ensure apply path requires ALLOW_009_UPGRADE, not ALLOW_008_UPGRADE
if awk '
  /CHECKPOINT D — APPLY 009|CHECKPOINT D — APPLY 009/ {in_apply=1}
  in_apply && /ALLOW_009_UPGRADE/ {seen009=1}
  in_apply && /refuse upgrade: ALLOW_008_UPGRADE/ {bad=1}
  in_apply && /^section |^########/ && !/APPLY 009/ {in_apply=0}
  END { if (bad) exit 2; if (!seen009) exit 3; exit 0 }
' "$SCR"; then
  ok "APPLY_USES_ALLOW_009_NOT_008"
else
  ko "APPLY_USES_ALLOW_009_NOT_008"
fi

bash -n "$SCR" && ok "BASH_SYNTAX_RELEASE_SCRIPT" || ko "BASH_SYNTAX_RELEASE_SCRIPT"
bash -n "$LIB" && ok "BASH_SYNTAX_INTEGRITY_LIB" || ko "BASH_SYNTAX_INTEGRITY_LIB"

rm -f "$non"
echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
