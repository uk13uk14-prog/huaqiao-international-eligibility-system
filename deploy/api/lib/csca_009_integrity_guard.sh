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
