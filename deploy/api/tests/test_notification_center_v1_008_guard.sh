#!/usr/bin/env bash
# Regression: 008 schema guard must use ONLY 008 tables; cover states A/B/C/D.
set -u
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCR="${ROOT}/deploy/api/m1-notification-center-v1-production-release.sh"
LIB="${ROOT}/deploy/api/lib/notification_008_schema_guard.sh"
N_PASS=0
N_FAIL=0
ok() { echo "PASS: $*"; N_PASS=$((N_PASS + 1)); }
ko() { echo "FAIL: $*"; N_FAIL=$((N_FAIL + 1)); }

[[ -f "$SCR" ]] || { echo "missing $SCR"; exit 1; }
[[ -f "$LIB" ]] || { echo "missing $LIB"; exit 1; }

# shellcheck source=deploy/api/lib/notification_008_schema_guard.sh
source "$LIB"

expect_state() {
  local name="$1" want_clean="$2" want_partial="$3" want_already="$4" want_inc="$5" want_allow="$6" want_mpi="$7"
  local fail=0
  [[ "${CLEAN_PRE_008}" == "${want_clean}" ]] || { echo "  CLEAN_PRE_008=${CLEAN_PRE_008} want ${want_clean}"; fail=1; }
  [[ "${PARTIAL_008}" == "${want_partial}" ]] || { echo "  PARTIAL_008=${PARTIAL_008} want ${want_partial}"; fail=1; }
  [[ "${ALREADY_UPGRADED}" == "${want_already}" ]] || { echo "  ALREADY_UPGRADED=${ALREADY_UPGRADED} want ${want_already}"; fail=1; }
  [[ "${INCONSISTENT_008}" == "${want_inc}" ]] || { echo "  INCONSISTENT_008=${INCONSISTENT_008} want ${want_inc}"; fail=1; }
  [[ "${ALLOW_008_UPGRADE}" == "${want_allow}" ]] || { echo "  ALLOW_008_UPGRADE=${ALLOW_008_UPGRADE} want ${want_allow}"; fail=1; }
  [[ "${MIGRATION_PARTIAL_OR_INCONSISTENT}" == "${want_mpi}" ]] || { echo "  MPI=${MIGRATION_PARTIAL_OR_INCONSISTENT} want ${want_mpi}"; fail=1; }
  if [[ "${fail}" -eq 0 ]]; then ok "state ${name}"; else ko "state ${name}"; fi
}

# A) revision=007, no 008 tables
classify_008_schema_state "007_admin_ai_expert_v1" NO NO NO NO
expect_state A YES NO NO NO YES NO
[[ "${SCHEMA_STATE}" == "A_CLEAN_PRE_008" ]] && ok "SCHEMA_STATE A" || ko "SCHEMA_STATE A=${SCHEMA_STATE}"

# B) revision=007, some 008 tables
classify_008_schema_state "007_admin_ai_expert_v1" YES NO NO NO
expect_state B NO YES NO NO NO YES
[[ "${SCHEMA_STATE}" == "B_PARTIAL_008" ]] && ok "SCHEMA_STATE B" || ko "SCHEMA_STATE B=${SCHEMA_STATE}"

# B2) revision=007, all 008 tables (still partial stamp)
classify_008_schema_state "007_admin_ai_expert_v1" YES YES YES YES
expect_state B_all NO YES NO NO NO YES

# C) revision=008, all 008 tables
classify_008_schema_state "008_notification_center_v1" YES YES YES YES
expect_state C NO NO YES NO NO NO
[[ "${SCHEMA_STATE}" == "C_ALREADY_008" ]] && ok "SCHEMA_STATE C" || ko "SCHEMA_STATE C=${SCHEMA_STATE}"

# D) revision=008, missing 008 tables
classify_008_schema_state "008_notification_center_v1" YES YES NO NO
expect_state D NO NO NO YES NO YES
[[ "${SCHEMA_STATE}" == "D_INCONSISTENT" ]] && ok "SCHEMA_STATE D" || ko "SCHEMA_STATE D=${SCHEMA_STATE}"

# D2) revision=008, zero 008 tables
classify_008_schema_state "008_notification_center_v1" NO NO NO NO
expect_state D_none NO NO NO YES NO YES

# False-positive regression: 007 objects must NOT appear in classify inputs / partial logic
non="$(mktemp)"
grep -vE '^[[:space:]]*#' "$SCR" >"$non" || true

# The 007-era false positive: marking partial when ai_provider/audit_events exist on 007
if grep -nE 'MIGRATION_PARTIAL_OR_INCONSISTENT=YES' "$non" | grep -q 'ai_provider\|audit_events\|HAS_AIP\|AE_EXISTS'; then
  ko "007 columns still drive MIGRATION_PARTIAL assignment"
else
  ok "007 columns do not drive MIGRATION_PARTIAL assignment"
fi

# Ensure classify is used
grep -q 'classify_008_schema_state' "$SCR" && ok "script calls classify_008_schema_state" || ko "missing classify call"
grep -q 'notification_008_schema_guard.sh' "$SCR" && ok "script sources 008 guard lib" || ko "missing guard source"
grep -q '007_SCHEMA_USED_FOR_008_PARTIAL_DETECT=NO' "$SCR" && ok "explicit 007-not-used flag" || ko "missing 007-not-used flag"

# 008 table checks present
for t in notifications notification_rules notification_devices notification_preferences; do
  grep -q "table_name='${t}'" "$SCR" && ok "checks table ${t}" || ko "missing table check ${t}"
done

# APPLY label fixed
if grep -q 'CHECKPOINT D — APPLY 008' "$SCR"; then
  ok "APPLY label says 008"
else
  ko "APPLY label missing 008"
fi
if grep -nE 'CHECKPOINT D — APPLY 007' "$SCR"; then
  ko "APPLY label still says 007"
else
  ok "no APPLY 007 residual label"
fi

# Must not use 007 columns as 008 partial gate in the classify block path
# (info-only echoes of 007 columns are allowed)
if awk '
  /classify_008_schema_state/ { in_call=1 }
  in_call && /ai_provider|audit_events/ { bad=1 }
  in_call && /^[[:space:]]*echo "MIGRATION_PARTIAL/ { in_call=0 }
  END { exit bad?0:1 }
' "$non"; then
  ko "classify call path references 007 markers"
else
  ok "classify call path free of 007 markers"
fi

bash -n "$SCR" && ok "bash -n release script" || ko "bash -n release script failed"
bash -n "$LIB" && ok "bash -n guard lib" || ko "bash -n guard lib failed"

rm -f "$non"
echo "----"
echo "PASSED=${N_PASS} FAILED=${N_FAIL}"
[[ "$N_FAIL" -eq 0 ]]
