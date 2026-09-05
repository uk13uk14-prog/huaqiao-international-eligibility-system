#!/usr/bin/env bash
# Pure helpers for Student CRM 010 release gate (no DB I/O).
# Independent of ALLOW_008_UPGRADE / CLEAN_PRE_008 / PARTIAL_009 / ALLOW_009_UPGRADE.
#
# Real 010 schema (alembic 010_student_crm_v1.py):
#   table  student_follow_ups
#   cols on student_master_profiles:
#     assignee_user_id, assigned_at, assigned_by_user_id,
#     crm_stage, risk_level, next_action,
#     next_follow_up_at, last_follow_up_at, identity_track
#
# Ops checklist aliases (echo keys) map onto those real objects.

crm010_is_nonneg_int() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

crm010_yes_count() {
  local n=0 f
  for f in "$@"; do
    [[ "${f}" == "YES" ]] && n=$((n + 1))
  done
  echo "${n}"
}

crm010_emit_diagnostic_keys() {
  local rev="${1:-}"
  echo "DB_REVISION_010_GATE=${rev}"
  # Canonical (real migration) keys
  echo "010_HAS_student_follow_ups=${CRM010_HAS_FOLLOW_UPS}"
  echo "010_HAS_assignee_user_id=${CRM010_HAS_ASSIGNEE_USER_ID}"
  echo "010_HAS_assigned_at=${CRM010_HAS_ASSIGNED_AT}"
  echo "010_HAS_assigned_by_user_id=${CRM010_HAS_ASSIGNED_BY_USER_ID}"
  echo "010_HAS_crm_stage=${CRM010_HAS_CRM_STAGE}"
  echo "010_HAS_risk_level=${CRM010_HAS_RISK_LEVEL}"
  echo "010_HAS_next_action=${CRM010_HAS_NEXT_ACTION}"
  echo "010_HAS_next_follow_up_at=${CRM010_HAS_NEXT_FOLLOW_UP_AT}"
  echo "010_HAS_last_follow_up_at=${CRM010_HAS_LAST_FOLLOW_UP_AT}"
  echo "010_HAS_identity_track=${CRM010_HAS_IDENTITY_TRACK}"
  # Ops checklist aliases (same YES/NO as mapped real objects)
  echo "010_HAS_student_follow_ups=${CRM010_HAS_FOLLOW_UPS}"
  echo "010_HAS_assignee_user_id=${CRM010_HAS_ASSIGNEE_USER_ID}"
  echo "010_HAS_assigned_at=${CRM010_HAS_ASSIGNED_AT}"
  echo "010_HAS_assigned_by_user_id=${CRM010_HAS_ASSIGNED_BY_USER_ID}"
  echo "010_HAS_crm_stage=${CRM010_HAS_CRM_STAGE}"
  echo "010_HAS_risk_level=${CRM010_HAS_RISK_LEVEL}"
  echo "010_HAS_next_action=${CRM010_HAS_NEXT_ACTION}"
  echo "010_HAS_next_follow_up_at=${CRM010_HAS_NEXT_FOLLOW_UP_AT}"
  echo "010_HAS_last_follow_up_at=${CRM010_HAS_LAST_FOLLOW_UP_AT}"
  echo "010_HAS_identity_track=${CRM010_HAS_IDENTITY_TRACK}"
  echo "010_OBJECT_PRESENT_COUNT=${CRM010_OBJECT_PRESENT_COUNT}"
  echo "010_OBJECT_EXPECTED_COUNT=${CRM010_OBJECT_EXPECTED_COUNT}"
  echo "SCHEMA_STATE_010=${SCHEMA_STATE_010}"
  echo "CLEAN_PRE_010=${CLEAN_PRE_010}"
  echo "PARTIAL_010=${PARTIAL_010}"
  echo "ALREADY_UPGRADED_010=${ALREADY_UPGRADED_010}"
  echo "INCONSISTENT_010=${INCONSISTENT_010}"
  echo "ALLOW_010_UPGRADE=${ALLOW_010_UPGRADE}"
  echo "SKIP_010_MIGRATE=${SKIP_010_MIGRATE}"
  echo "OLD_008_GATE_NOT_USED_FOR_010_APPLY=YES"
  echo "OLD_009_GATE_NOT_USED_FOR_010_APPLY=YES"
}

# classify_010_release_state \
#   <revision> \
#   <has_notifications> <has_notification_rules> <has_notification_devices> <has_notification_preferences> \
#   <total_rules> <csca_rules> <non_csca_rules> \
#   <has_follow_ups> \
#   <has_assignee_user_id> <has_assigned_at> <has_assigned_by_user_id> \
#   <has_crm_stage> <has_risk_level> <has_next_action> \
#   <has_next_follow_up_at> <has_last_follow_up_at> <has_identity_track>
classify_010_release_state() {
  local rev="${1:-}"
  local has_n="${2:-NO}"
  local has_nr="${3:-NO}"
  local has_nd="${4:-NO}"
  local has_np="${5:-NO}"
  local total="${6:-}"
  local csca="${7:-}"
  local non_csca="${8:-}"
  local has_fu="${9:-NO}"
  local has_assignee="${10:-NO}"
  local has_assigned_at="${11:-NO}"
  local has_assigned_by="${12:-NO}"
  local has_crm_stage="${13:-NO}"
  local has_risk="${14:-NO}"
  local has_next_action="${15:-NO}"
  local has_next_fu="${16:-NO}"
  local has_last_fu="${17:-NO}"
  local has_identity="${18:-NO}"

  # Prefer release-script EXPECTED_BEFORE/AFTER when present.
  local expected_before="${EXPECTED_BEFORE_010:-${EXPECTED_BEFORE:-009_csca_notification_rules}}"
  local expected_after="${EXPECTED_AFTER_010:-${EXPECTED_AFTER:-010_student_crm_v1}}"
  local expected_rules="${EXPECTED_POST_NOTIFICATION_RULES:-51}"
  local expected_csca="${EXPECTED_CSCA_RULES:-24}"
  local expected_non_csca="${EXPECTED_NON_CSCA_RULES:-27}"

  CLEAN_PRE_010=NO
  PARTIAL_010=NO
  ALREADY_UPGRADED_010=NO
  INCONSISTENT_010=NO
  ALLOW_010_UPGRADE=NO
  SKIP_010_MIGRATE=NO
  SCHEMA_STATE_010=UNKNOWN

  CRM010_HAS_FOLLOW_UPS="${has_fu}"
  CRM010_HAS_ASSIGNEE_USER_ID="${has_assignee}"
  CRM010_HAS_ASSIGNED_AT="${has_assigned_at}"
  CRM010_HAS_ASSIGNED_BY_USER_ID="${has_assigned_by}"
  CRM010_HAS_CRM_STAGE="${has_crm_stage}"
  CRM010_HAS_RISK_LEVEL="${has_risk}"
  CRM010_HAS_NEXT_ACTION="${has_next_action}"
  CRM010_HAS_NEXT_FOLLOW_UP_AT="${has_next_fu}"
  CRM010_HAS_LAST_FOLLOW_UP_AT="${has_last_fu}"
  CRM010_HAS_IDENTITY_TRACK="${has_identity}"

  CRM010_OBJECT_EXPECTED_COUNT=10
  CRM010_OBJECT_PRESENT_COUNT="$(crm010_yes_count \
    "${has_fu}" \
    "${has_assignee}" "${has_assigned_at}" "${has_assigned_by}" \
    "${has_crm_stage}" "${has_risk}" "${has_next_action}" \
    "${has_next_fu}" "${has_last_fu}" "${has_identity}")"

  local notif_ok=NO
  if [[ "${has_n}" == "YES" && "${has_nr}" == "YES" && "${has_nd}" == "YES" && "${has_np}" == "YES" ]]; then
    notif_ok=YES
  fi

  local rules_ok=NO
  if ! crm010_is_nonneg_int "${total}" || ! crm010_is_nonneg_int "${csca}" || ! crm010_is_nonneg_int "${non_csca}"; then
    INCONSISTENT_010=YES
    SCHEMA_STATE_010=D_INCONSISTENT_010
    crm010_emit_diagnostic_keys "${rev}"
    return 1
  fi
  if [[ "${total}" == "${expected_rules}" && "${csca}" == "${expected_csca}" && "${non_csca}" == "${expected_non_csca}" ]]; then
    rules_ok=YES
  fi

  if [[ "${notif_ok}" != "YES" || "${rules_ok}" != "YES" ]]; then
    INCONSISTENT_010=YES
    SCHEMA_STATE_010=D_INCONSISTENT_010
    crm010_emit_diagnostic_keys "${rev}"
    return 0
  fi

  if [[ "${rev}" != "${expected_before}" && "${rev}" != "${expected_after}" ]]; then
    INCONSISTENT_010=YES
    SCHEMA_STATE_010=D_INCONSISTENT_010
    crm010_emit_diagnostic_keys "${rev}"
    return 0
  fi

  if [[ "${rev}" == "${expected_before}" ]]; then
    if [[ "${CRM010_OBJECT_PRESENT_COUNT}" -eq 0 ]]; then
      CLEAN_PRE_010=YES
      ALLOW_010_UPGRADE=YES
      SCHEMA_STATE_010=A_CLEAN_PRE_010
    else
      PARTIAL_010=YES
      SCHEMA_STATE_010=C_PARTIAL_010
    fi
  else
    if [[ "${CRM010_OBJECT_PRESENT_COUNT}" -eq "${CRM010_OBJECT_EXPECTED_COUNT}" ]]; then
      ALREADY_UPGRADED_010=YES
      SKIP_010_MIGRATE=YES
      SCHEMA_STATE_010=B_ALREADY_010
    else
      PARTIAL_010=YES
      SCHEMA_STATE_010=C_PARTIAL_010
    fi
  fi

  crm010_emit_diagnostic_keys "${rev}"
  return 0
}
