#!/usr/bin/env bash
# Unit tests: CSCA V1 production release dynamic user integrity gate.
# No production DB access. Pure helper + static script assertions.
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

EXPECTED_UNI=125
EXPECTED_TL=900
EXPECTED_PRE_NOTIFICATION_RULES=27
EXPECTED_CSCA_RULES=24
EXPECTED_POST_NOTIFICATION_RULES=51
EXPECTED_NON_CSCA_RULES=27

expect_pass() {
  local name="$1"
  shift
  if "$@"; then
    ok "$name"
  else
    ko "$name (expected PASS)"
  fi
}

expect_fail() {
  local name="$1"
  shift
  if "$@"; then
    ko "$name (expected FAIL CLOSED)"
  else
    ok "$name"
  fi
}

# 1) PRE=2 POST=2 PASS
expect_pass "USER_COUNT_2_TEST" \
  validate_post_integrity 2 2 125 125 900 900 51 24 27

# 2) PRE=8 POST=8 PASS
expect_pass "USER_COUNT_8_TEST" \
  validate_post_integrity 8 8 125 125 900 900 51 24 27

# 3) PRE=800 POST=800 PASS
expect_pass "USER_COUNT_800_TEST" \
  validate_post_integrity 800 800 125 125 900 900 51 24 27

# 4) PRE=8 POST=7 FAIL CLOSED
expect_fail "USER_LOSS_FAIL_CLOSED_TEST" \
  validate_post_integrity 8 7 125 125 900 900 51 24 27

# 5) universities != 125 FAIL CLOSED
expect_fail "UNIVERSITIES_NE_125_FAIL_CLOSED" \
  validate_post_integrity 8 8 125 124 900 900 51 24 27
expect_fail "PRE_UNIVERSITIES_NE_125_FAIL_CLOSED" \
  validate_pre_fingerprint 124 900 8 27

# 6) timelines != 900 FAIL CLOSED
expect_fail "TIMELINES_NE_900_FAIL_CLOSED" \
  validate_post_integrity 8 8 125 125 900 899 51 24 27
expect_fail "PRE_TIMELINES_NE_900_FAIL_CLOSED" \
  validate_pre_fingerprint 125 899 8 27

# 7) POST_NOTIFICATION_RULE_COUNT != 51 FAIL CLOSED
expect_fail "NOTIFICATION_TOTAL_NE_51_FAIL_CLOSED" \
  validate_post_integrity 8 8 125 125 900 900 50 24 27

# 8) CSCA_RULE_COUNT != 24 FAIL CLOSED
expect_fail "CSCA_RULE_NE_24_FAIL_CLOSED" \
  validate_post_integrity 8 8 125 125 900 900 51 23 28

# 9) NON_CSCA_RULE_COUNT_AFTER != 27 FAIL CLOSED
expect_fail "NON_CSCA_PRESERVATION_NE_27_FAIL_CLOSED" \
  validate_post_integrity 8 8 125 125 900 900 51 24 26

# 10) diagnostic-only with USER_COUNT=8 must NOT fail because !=2
# Pre fingerprint accepts any nonneg user count; rules=27 on 008 baseline.
if validate_pre_fingerprint 125 900 8 27 >/dev/null; then
  ok "DIAGNOSTIC_USER_8_PRE_FINGERPRINT"
else
  ko "DIAGNOSTIC_USER_8_PRE_FINGERPRINT"
fi
if validate_pre_fingerprint 125 900 2 27 >/dev/null \
  && validate_pre_fingerprint 125 900 800 27 >/dev/null; then
  ok "DIAGNOSTIC_DYNAMIC_USER_ACCEPTS_2_AND_800"
else
  ko "DIAGNOSTIC_DYNAMIC_USER_ACCEPTS_2_AND_800"
fi

# Static: fixed EXPECTED_USERS fingerprint removed from release script
non="$(mktemp)"
grep -vE '^[[:space:]]*#' "$SCR" >"$non" || true
if grep -nE 'EXPECTED_USERS=|[[:space:]]\$\{EXPECTED_USERS\}' "$non"; then
  ko "FIXED_USER_COUNT_REMOVED (EXPECTED_USERS still referenced)"
else
  ok "FIXED_USER_COUNT_REMOVED"
fi
if grep -q 'EXPECTED_USERS=2' "$SCR"; then
  ko "OLD_EXPECTED_USERS_FIXED_2_GONE"
else
  ok "OLD_EXPECTED_USERS_FIXED_2_GONE"
fi
grep -q 'PRE_USER_COUNT=' "$SCR" && ok "DYNAMIC_PRE_USER_COUNT_PRESENT" || ko "DYNAMIC_PRE_USER_COUNT_PRESENT"
grep -q 'POST_USER_COUNT=' "$SCR" && ok "POST_USER_COUNT_COMPARE_PRESENT" || ko "POST_USER_COUNT_COMPARE_PRESENT"
grep -q 'validate_post_integrity' "$SCR" && ok "validate_post_integrity_wired" || ko "validate_post_integrity_wired"
grep -q 'csca_009_integrity_guard.sh' "$SCR" && ok "integrity_guard_sourced" || ko "integrity_guard_sourced"
grep -q 'EXPECTED_UNI=125' "$SCR" && ok "EXPECTED_UNIVERSITIES=125" || ko "EXPECTED_UNIVERSITIES=125"
grep -q 'EXPECTED_TL=900' "$SCR" && ok "EXPECTED_TIMELINES=900" || ko "EXPECTED_TIMELINES=900"
grep -q 'EXPECTED_PRE_NOTIFICATION_RULES=27' "$SCR" && ok "PRE_NOTIFICATION_RULE_COUNT_EXPECTED=27" || ko "PRE_RULES_27"
grep -q 'EXPECTED_CSCA_RULES=24' "$SCR" && ok "CSCA_RULE_COUNT_EXPECTED=24" || ko "CSCA_24"
grep -q 'EXPECTED_POST_NOTIFICATION_RULES=51' "$SCR" && ok "POST_NOTIFICATION_RULE_COUNT_EXPECTED=51" || ko "POST_51"
grep -q 'EXPECTED_NON_CSCA_RULES=27' "$SCR" && ok "NON_CSCA_RULE_COUNT_EXPECTED=27" || ko "NON_CSCA_27"
grep -q 'NON_CSCA_RULE_COUNT_AFTER' "$SCR" && ok "NON_CSCA_PRESERVATION_CHECK" || ko "NON_CSCA_PRESERVATION_CHECK"
grep -q -- '--checkpoint-d-diagnostic-only' "$SCR" && ok "DIAGNOSTIC_ONLY_FLAG" || ko "DIAGNOSTIC_ONLY_FLAG"
# diagnostic must not gate on users==2
if grep -nE 'users != 2|USER_COUNT != 2|USERS.*==.*2' "$non" | grep -viE 'PRE_USER|POST_USER|EXPECTED_PRE|EXPECTED_POST|CSCA_|RULE'; then
  ko "DIAGNOSTIC_STILL_GATES_USERS_EQ_2"
else
  ok "DIAGNOSTIC_NO_FIXED_USER_EQ_2_GATE"
fi

# Exact CSCA event types from 009
IN_LIST="$(csca_009_event_types_sql_in_list)"
case "${IN_LIST}" in
  *CSCA_REGISTRATION_DEADLINE*CSCA_EXAM_DATE*CSCA_RESULT_DATE*CSCA_PREPARATION*)
    ok "CSCA_EVENT_TYPES_MATCH_009"
    ;;
  *)
    ko "CSCA_EVENT_TYPES_MATCH_009 got=${IN_LIST}"
    ;;
esac

# Safety gates preserved (static)
grep -q 'huaqiao-postgres' "$SCR" && ok "PG_CONTAINER_huaqiao-postgres" || ko "PG_CONTAINER"
grep -q '5433' "$SCR" && ok "PORT_5433" || ko "PORT_5433"
grep -q 'SQLITE' "$SCR" && ok "SQLITE_BLOCK_PRESENT" || ko "SQLITE_BLOCK"
if grep -nE 'pg_restore[[:space:]]+[^-].*huaqiao|auto[[:space:]]*pg_restore' "$non" \
  | grep -viE 'pg_restore -l|abort|HINT|AUTO_PG_RESTORE=NO|Do NOT auto|NO automatic'; then
  ko "AUTO_PG_RESTORE_NOT_BLOCKED"
else
  ok "AUTO_PG_RESTORE_BLOCKED"
fi
grep -q '\.venv' "$SCR" && ok "VENV_REQUIRED" || ko "VENV_REQUIRED"

bash -n "$SCR" && ok "BASH_SYNTAX_RELEASE_SCRIPT" || ko "BASH_SYNTAX_RELEASE_SCRIPT"
bash -n "$LIB" && ok "BASH_SYNTAX_INTEGRITY_LIB" || ko "BASH_SYNTAX_INTEGRITY_LIB"

rm -f "$non"
echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "${N_FAIL}" -eq 0 ]]
