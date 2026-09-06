#!/usr/bin/env bash
# Pure helpers for CSCA 009 production release integrity gates (no DB I/O).
# Sourced by m1-csca-v1-production-release.sh and unit tests.
#
# USER COUNT is a DYNAMIC production baseline:
#   PRE_USER_COUNT  = count(*) FROM users before migration
#   POST_USER_COUNT = count(*) FROM users after migration
#   Require POST_USER_COUNT == PRE_USER_COUNT (never a fixed fingerprint like 2).
#
# Universities / timelines remain fixed fingerprints (125 / 900).
# Notification rules: 008 baseline 27 + 009 CSCA seeds 24 => 51; non-CSCA must stay 27.
#
# 009 release state machine is INDEPENDENT of 008 upgrade gates.
# SCHEMA_STATE=C_ALREADY_008 is a VALID base for 009 (BASE_008_SCHEMA_READY=YES).
# Never require ALLOW_008_UPGRADE / CLEAN_PRE_008 to apply 009.

# Exact event_type values from alembic/versions/009_csca_notification_rules.py
CSCA_009_EVENT_TYPES=(
  CSCA_REGISTRATION_DEADLINE
  CSCA_EXAM_DATE
  CSCA_RESULT_DATE
  CSCA_PREPARATION
)

csca_009_event_types_sql_in_list() {
  local first=1 et
  printf "("
  for et in "${CSCA_009_EVENT_TYPES[@]}"; do
    if [[ "${first}" -eq 1 ]]; then
      first=0
    else
      printf ","
    fi
    printf "'%s'" "${et}"
  done
  printf ")"
}

is_nonneg_int() {
  local v="${1:-}"
  [[ "${v}" =~ ^[0-9]+$ ]]
}

# validate_pre_fingerprint <uni> <tl> <users> <notification_rules>
# Fail closed on fixed uni/tl and invalid user count. Users are NOT compared to a fixed value.
# When rules is provided (non-empty), require rules == EXPECTED_PRE_NOTIFICATION_RULES (27).
validate_pre_fingerprint() {
  local uni="${1:-}"
  local tl="${2:-}"
  local users="${3:-}"
  local rules="${4:-}"
  local expected_uni="${EXPECTED_UNI:-125}"
  local expected_tl="${EXPECTED_TL:-900}"
  local expected_pre_rules="${EXPECTED_PRE_NOTIFICATION_RULES:-27}"

  if ! is_nonneg_int "${uni}"; then
    echo "PRE_FINGERPRINT_FAIL=universities_not_int:${uni}"
    return 1
  fi
  if ! is_nonneg_int "${tl}"; then
    echo "PRE_FINGERPRINT_FAIL=timelines_not_int:${tl}"
    return 1
  fi
  if ! is_nonneg_int "${users}"; then
    echo "PRE_FINGERPRINT_FAIL=users_not_nonneg_int:${users}"
    return 1
  fi
  if [[ "${uni}" != "${expected_uni}" ]]; then
    echo "PRE_FINGERPRINT_FAIL=universities:${uni}!=${expected_uni}"
    return 1
  fi
  if [[ "${tl}" != "${expected_tl}" ]]; then
    echo "PRE_FINGERPRINT_FAIL=timelines:${tl}!=${expected_tl}"
    return 1
  fi
  if [[ -n "${rules}" ]]; then
    if ! is_nonneg_int "${rules}"; then
      echo "PRE_FINGERPRINT_FAIL=notification_rules_not_int:${rules}"
      return 1
    fi
    if [[ "${rules}" != "${expected_pre_rules}" ]]; then
      echo "PRE_FINGERPRINT_FAIL=notification_rules:${rules}!=${expected_pre_rules}"
      return 1
    fi
  fi
  echo "PRE_FINGERPRINT_PASS=YES"
  echo "PRE_USER_COUNT=${users}"
  echo "PRE_UNIVERSITY_COUNT=${uni}"
  echo "PRE_TIMELINE_COUNT=${tl}"
  [[ -n "${rules}" ]] && echo "PRE_NOTIFICATION_RULE_COUNT=${rules}"
  return 0
}

# validate_post_integrity
#   <pre_users> <post_users>
#   <pre_uni> <post_uni>
#   <pre_tl> <post_tl>
#   <post_rules> <csca_rules> <non_csca_rules>
validate_post_integrity() {
  local pre_users="${1:-}"
  local post_users="${2:-}"
  local pre_uni="${3:-}"
  local post_uni="${4:-}"
  local pre_tl="${5:-}"
  local post_tl="${6:-}"
  local post_rules="${7:-}"
  local csca_rules="${8:-}"
  local non_csca_rules="${9:-}"

  local expected_uni="${EXPECTED_UNI:-125}"
  local expected_tl="${EXPECTED_TL:-900}"
  local expected_post_rules="${EXPECTED_POST_NOTIFICATION_RULES:-51}"
  local expected_csca="${EXPECTED_CSCA_RULES:-24}"
  local expected_non_csca="${EXPECTED_NON_CSCA_RULES:-27}"

  for v in "${pre_users}" "${post_users}" "${pre_uni}" "${post_uni}" "${pre_tl}" "${post_tl}" \
           "${post_rules}" "${csca_rules}" "${non_csca_rules}"; do
    if ! is_nonneg_int "${v}"; then
      echo "POST_INTEGRITY_FAIL=not_nonneg_int:${v}"
      return 1
    fi
  done

  if [[ "${post_users}" != "${pre_users}" ]]; then
    echo "POST_INTEGRITY_FAIL=users_changed:${pre_users}->${post_users}"
    return 1
  fi
  if [[ "${post_uni}" != "${pre_uni}" || "${post_uni}" != "${expected_uni}" ]]; then
    echo "POST_INTEGRITY_FAIL=universities:${post_uni} (pre=${pre_uni} expected=${expected_uni})"
    return 1
  fi
  if [[ "${post_tl}" != "${pre_tl}" || "${post_tl}" != "${expected_tl}" ]]; then
    echo "POST_INTEGRITY_FAIL=timelines:${post_tl} (pre=${pre_tl} expected=${expected_tl})"
    return 1
  fi
  if [[ "${post_rules}" != "${expected_post_rules}" ]]; then
    echo "POST_INTEGRITY_FAIL=notification_rules_total:${post_rules}!=${expected_post_rules}"
    return 1
  fi
  if [[ "${csca_rules}" != "${expected_csca}" ]]; then
    echo "POST_INTEGRITY_FAIL=csca_rules:${csca_rules}!=${expected_csca}"
    return 1
  fi
  if [[ "${non_csca_rules}" != "${expected_non_csca}" ]]; then
    echo "POST_INTEGRITY_FAIL=non_csca_rules:${non_csca_rules}!=${expected_non_csca}"
    return 1
  fi
  # Arithmetic consistency: total == csca + non_csca
  if [[ "$((csca_rules + non_csca_rules))" -ne "${post_rules}" ]]; then
    echo "POST_INTEGRITY_FAIL=rules_sum_mismatch:csca(${csca_rules})+non(${non_csca_rules})!=total(${post_rules})"
    return 1
  fi

  echo "POST_INTEGRITY_PASS=YES"
  echo "POST_USER_COUNT=${post_users}"
  echo "POST_UNIVERSITY_COUNT=${post_uni}"
  echo "POST_TIMELINE_COUNT=${post_tl}"
  echo "POST_NOTIFICATION_RULE_COUNT=${post_rules}"
  echo "CSCA_RULE_COUNT=${csca_rules}"
  echo "NON_CSCA_RULE_COUNT_AFTER=${non_csca_rules}"
  return 0
}

# evaluate_base_008_schema_ready <schema_state_008> <object_present_count> [revision]
# For 009 release: C_ALREADY_008 + 4/4 tables => BASE_008_SCHEMA_READY=YES.
# When revision is already 009, 4/4 tables alone is sufficient base readiness.
evaluate_base_008_schema_ready() {
  local schema_state="${1:-}"
  local present_count="${2:-0}"
  local rev="${3:-}"
  local expected_after="${EXPECTED_AFTER:-009_csca_notification_rules}"
  BASE_008_SCHEMA_READY=NO
  if [[ "${present_count}" == "4" ]]; then
    if [[ "${schema_state}" == "C_ALREADY_008" ]]; then
      BASE_008_SCHEMA_READY=YES
    elif [[ "${rev}" == "${expected_after}" ]]; then
      BASE_008_SCHEMA_READY=YES
    fi
  fi
  echo "BASE_008_SCHEMA_READY=${BASE_008_SCHEMA_READY}"
  [[ "${BASE_008_SCHEMA_READY}" == "YES" ]]
}


# classify_009_release_state <revision> <csca_count> <non_csca_count> <total_count>
# Independent of ALLOW_008_UPGRADE / CLEAN_PRE_008.
# Sets:
#   CLEAN_PRE_009 PARTIAL_009 ALREADY_UPGRADED_009 INCONSISTENT_009
#   ALLOW_009_UPGRADE SKIP_009_MIGRATE SCHEMA_STATE_009
classify_009_release_state() {
  local rev="${1:-}"
  local csca="${2:-}"
  local non_csca="${3:-}"
  local total="${4:-}"
  local expected_before="${EXPECTED_BEFORE:-008_notification_center_v1}"
  local expected_after="${EXPECTED_AFTER:-009_csca_notification_rules}"
  local expected_pre_rules="${EXPECTED_PRE_NOTIFICATION_RULES:-27}"
  local expected_csca="${EXPECTED_CSCA_RULES:-24}"
  local expected_non_csca="${EXPECTED_NON_CSCA_RULES:-27}"
  local expected_post_rules="${EXPECTED_POST_NOTIFICATION_RULES:-51}"

  CLEAN_PRE_009=NO
  PARTIAL_009=NO
  ALREADY_UPGRADED_009=NO
  INCONSISTENT_009=NO
  ALLOW_009_UPGRADE=NO
  SKIP_009_MIGRATE=NO
  SCHEMA_STATE_009=UNKNOWN

  if ! is_nonneg_int "${csca}" || ! is_nonneg_int "${non_csca}" || ! is_nonneg_int "${total}"; then
    INCONSISTENT_009=YES
    SCHEMA_STATE_009=D_INCONSISTENT_009
    echo "SCHEMA_STATE_009=${SCHEMA_STATE_009}"
    echo "INCONSISTENT_009=YES"
    return 1
  fi

  if [[ "${rev}" == "${expected_before}" ]]; then
    if [[ "${csca}" == "0" && "${non_csca}" == "${expected_non_csca}" && "${total}" == "${expected_pre_rules}" ]]; then
      # A) clean pre-009 — normal apply path
      CLEAN_PRE_009=YES
      ALLOW_009_UPGRADE=YES
      SCHEMA_STATE_009=A_CLEAN_PRE_009
    elif [[ "${csca}" != "0" && "${csca}" != "${expected_csca}" ]]; then
      # B) partial CSCA seed while still on 008
      PARTIAL_009=YES
      SCHEMA_STATE_009=B_PARTIAL_009
    elif [[ "${csca}" == "${expected_csca}" && "${non_csca}" == "${expected_non_csca}" && "${total}" == "${expected_post_rules}" ]]; then
      # Data looks fully seeded but revision still 008 — treat as partial/inconsistent stamp gap
      PARTIAL_009=YES
      SCHEMA_STATE_009=B_PARTIAL_009
    else
      INCONSISTENT_009=YES
      SCHEMA_STATE_009=D_INCONSISTENT_009
    fi
  elif [[ "${rev}" == "${expected_after}" ]]; then
    if [[ "${csca}" == "${expected_csca}" && "${non_csca}" == "${expected_non_csca}" && "${total}" == "${expected_post_rules}" ]]; then
      # C) already upgraded — do not re-migrate
      ALREADY_UPGRADED_009=YES
      SKIP_009_MIGRATE=YES
      SCHEMA_STATE_009=C_ALREADY_009
    else
      # D) stamped 009 but rule counts wrong
      INCONSISTENT_009=YES
      SCHEMA_STATE_009=D_INCONSISTENT_009
    fi
  else
    INCONSISTENT_009=YES
    SCHEMA_STATE_009=UNEXPECTED_REVISION
  fi

  echo "SCHEMA_STATE_009=${SCHEMA_STATE_009}"
  echo "CLEAN_PRE_009=${CLEAN_PRE_009}"
  echo "PARTIAL_009=${PARTIAL_009}"
  echo "ALREADY_UPGRADED_009=${ALREADY_UPGRADED_009}"
  echo "INCONSISTENT_009=${INCONSISTENT_009}"
  echo "ALLOW_009_UPGRADE=${ALLOW_009_UPGRADE}"
  echo "SKIP_009_MIGRATE=${SKIP_009_MIGRATE}"
  return 0
}
