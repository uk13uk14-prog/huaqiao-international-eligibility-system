#!/usr/bin/env bash
# Pure helpers for Admin Console V2 011 release gate (no DB I/O).
# Independent of 008/009/010 apply flags.
#
# Real 011 schema (alembic 011_admin_console_v2.py):
#   cols on users: account_kind, job_title, last_login_at, must_change_password
#   index: ix_users_account_kind
# No new tables / FKs / enums / check constraints.

admin011_yes_count() {
  local n=0 f
  for f in "$@"; do
    [[ "${f}" == "YES" ]] && n=$((n + 1))
  done
  echo "${n}"
}

admin011_emit_diagnostic_keys() {
  local rev="${1:-}"
  echo "DB_REVISION_011_GATE=${rev}"
  echo "011_HAS_account_kind=${ADMIN011_HAS_ACCOUNT_KIND}"
  echo "011_HAS_job_title=${ADMIN011_HAS_JOB_TITLE}"
  echo "011_HAS_last_login_at=${ADMIN011_HAS_LAST_LOGIN_AT}"
  echo "011_HAS_must_change_password=${ADMIN011_HAS_MUST_CHANGE_PASSWORD}"
  echo "011_HAS_ix_users_account_kind=${ADMIN011_HAS_INDEX}"
  echo "011_OBJECT_PRESENT_COUNT=${ADMIN011_OBJECT_PRESENT_COUNT}"
  echo "011_OBJECT_EXPECTED_COUNT=${ADMIN011_OBJECT_EXPECTED_COUNT}"
  echo "SCHEMA_STATE_011=${SCHEMA_STATE_011}"
  echo "CLEAN_PRE_011=${CLEAN_PRE_011}"
  echo "PARTIAL_011=${PARTIAL_011}"
  echo "ALREADY_UPGRADED_011=${ALREADY_UPGRADED_011}"
  echo "INCONSISTENT_011=${INCONSISTENT_011}"
  echo "ALLOW_011_UPGRADE=${ALLOW_011_UPGRADE}"
  echo "SKIP_011_MIGRATE=${SKIP_011_MIGRATE}"
  echo "OLD_010_GATE_NOT_USED_FOR_011_APPLY=YES"
}

# classify_011_release_state \
#   <revision> \
#   <total_rules> <csca_rules> <non_csca_rules> \
#   <has_account_kind> <has_job_title> <has_last_login_at> <has_must_change_password> <has_index>
classify_011_release_state() {
  local rev="${1:-}"
  local total="${2:-}"
  local csca="${3:-}"
  local non_csca="${4:-}"
  local has_kind="${5:-NO}"
  local has_title="${6:-NO}"
  local has_login="${7:-NO}"
  local has_must="${8:-NO}"
  local has_idx="${9:-NO}"

  local expected_before="${EXPECTED_BEFORE_011:-${EXPECTED_BEFORE:-010_student_crm_v1}}"
  local expected_after="${EXPECTED_AFTER_011:-${EXPECTED_AFTER:-011_admin_console_v2}}"
  local expected_rules="${EXPECTED_POST_NOTIFICATION_RULES:-51}"
  local expected_csca="${EXPECTED_CSCA_RULES:-24}"
  local expected_non_csca="${EXPECTED_NON_CSCA_RULES:-27}"

  CLEAN_PRE_011=NO
  PARTIAL_011=NO
  ALREADY_UPGRADED_011=NO
  INCONSISTENT_011=NO
  ALLOW_011_UPGRADE=NO
  SKIP_011_MIGRATE=NO
  SCHEMA_STATE_011=UNKNOWN

  ADMIN011_HAS_ACCOUNT_KIND="${has_kind}"
  ADMIN011_HAS_JOB_TITLE="${has_title}"
  ADMIN011_HAS_LAST_LOGIN_AT="${has_login}"
  ADMIN011_HAS_MUST_CHANGE_PASSWORD="${has_must}"
  ADMIN011_HAS_INDEX="${has_idx}"
  ADMIN011_OBJECT_EXPECTED_COUNT=5
  ADMIN011_OBJECT_PRESENT_COUNT="$(admin011_yes_count \
    "${has_kind}" "${has_title}" "${has_login}" "${has_must}" "${has_idx}")"

  local rules_ok=NO
  if [[ "${total}" == "${expected_rules}" && "${csca}" == "${expected_csca}" && "${non_csca}" == "${expected_non_csca}" ]]; then
    rules_ok=YES
  fi

  if [[ "${rules_ok}" != "YES" ]]; then
    INCONSISTENT_011=YES
    SCHEMA_STATE_011=D_INCONSISTENT_011
  elif [[ "${rev}" == "${expected_after}" && "${ADMIN011_OBJECT_PRESENT_COUNT}" -eq 5 ]]; then
    ALREADY_UPGRADED_011=YES
    SKIP_011_MIGRATE=YES
    SCHEMA_STATE_011=B_ALREADY_011
  elif [[ "${rev}" == "${expected_before}" && "${ADMIN011_OBJECT_PRESENT_COUNT}" -eq 0 ]]; then
    CLEAN_PRE_011=YES
    ALLOW_011_UPGRADE=YES
    SCHEMA_STATE_011=A_CLEAN_PRE_011
  elif [[ "${ADMIN011_OBJECT_PRESENT_COUNT}" -gt 0 && "${ADMIN011_OBJECT_PRESENT_COUNT}" -lt 5 ]]; then
    PARTIAL_011=YES
    SCHEMA_STATE_011=C_PARTIAL_011
  elif [[ "${rev}" == "${expected_after}" ]]; then
    PARTIAL_011=YES
    SCHEMA_STATE_011=C_PARTIAL_011
  elif [[ "${rev}" != "${expected_before}" && "${rev}" != "${expected_after}" ]]; then
    INCONSISTENT_011=YES
    SCHEMA_STATE_011=D_INCONSISTENT_011
  else
    INCONSISTENT_011=YES
    SCHEMA_STATE_011=D_INCONSISTENT_011
  fi

  admin011_emit_diagnostic_keys "${rev}"
}

# Staff/customer backfill policy (011 adds metadata only; does not change users.role):
#   PRE_STAFF = count(role in admin|super_admin|operations_admin|consultant|support)
#   PRE_CUSTOMER = PRE_USER_COUNT - PRE_STAFF
#   After: account_kind=STAFF iff role already in that set; everyone else CUSTOMER.
#   Existing member/customer cannot gain admin login. Existing admin keeps console.
#   Require POST_USER==PRE_USER, POST_CUSTOMER==PRE_CUSTOMER,
#   POST_STAFF>=PRE_STAFF and POST_STAFF==PRE_STAFF (no silent customer→staff).
# validate_011_account_kind_integrity <pre_users> <pre_staff_by_role> <post_users> <post_staff> <post_customer> <illegal_staff>
validate_011_account_kind_integrity() {
  local pre_users="${1:-}"
  local pre_staff="${2:-}"
  local post_users="${3:-}"
  local post_staff="${4:-}"
  local post_customer="${5:-}"
  local illegal="${6:-}"
  local expected_customer=$((pre_users - pre_staff))

  if [[ "${post_users}" != "${pre_users}" ]]; then
    echo "ACCOUNT_KIND_INTEGRITY_FAIL=user_count_changed:${pre_users}->${post_users}"
    return 1
  fi
  if ! [[ "${post_staff}" =~ ^[0-9]+$ && "${pre_staff}" =~ ^[0-9]+$ ]]; then
    echo "ACCOUNT_KIND_INTEGRITY_FAIL=staff_not_int:${pre_staff}->${post_staff}"
    return 1
  fi
  if [[ "${post_staff}" -lt "${pre_staff}" ]]; then
    echo "ACCOUNT_KIND_INTEGRITY_FAIL=staff_lost:${pre_staff}->${post_staff}"
    return 1
  fi
  if [[ "${post_staff}" -gt "${pre_staff}" ]]; then
    echo "ACCOUNT_KIND_INTEGRITY_FAIL=staff_grew_without_role_source:${pre_staff}->${post_staff}"
    return 1
  fi
  if [[ "${post_customer}" != "${expected_customer}" ]]; then
    echo "ACCOUNT_KIND_INTEGRITY_FAIL=customer_flipped:${expected_customer}->${post_customer}"
    return 1
  fi
  if [[ "${illegal}" != "0" ]]; then
    echo "ACCOUNT_KIND_INTEGRITY_FAIL=customer_marked_staff:${illegal}"
    return 1
  fi
  echo "ACCOUNT_KIND_INTEGRITY=PASS"
  echo "PRE_STAFF_COUNT=${pre_staff}"
  echo "POST_STAFF_COUNT=${post_staff}"
  echo "PRE_CUSTOMER_COUNT=${expected_customer}"
  echo "POST_CUSTOMER_COUNT=${post_customer}"
  return 0
}
