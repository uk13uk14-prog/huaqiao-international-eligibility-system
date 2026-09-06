#!/usr/bin/env bash
# Pure helpers for Notification Center 008 schema guard (no DB I/O).
# Sourced by production release script and unit tests.
#
# 008 migration creates ONLY these tables (read from 008_notification_center_v1.py):
#   notifications, notification_rules, notification_devices, notification_preferences
# 007 objects (expert_consultations.student_id / ai_provider, eligibility_records.student_id,
# audit_events) must NEVER feed 008 partial detection.

# classify_008_schema_state <revision> <notifications> <rules> <devices> <prefs>
# Each table flag is YES or NO.
# Sets: CLEAN_PRE_008 PARTIAL_008 ALREADY_UPGRADED INCONSISTENT_008
#       MIGRATION_PARTIAL_OR_INCONSISTENT ALLOW_008_UPGRADE SCHEMA_STATE
#       N008_OBJECT_PRESENT_COUNT N008_OBJECTS_EXPECTED=4
classify_008_schema_state() {
  local rev="${1:-}"
  local has_n="${2:-NO}"
  local has_nr="${3:-NO}"
  local has_nd="${4:-NO}"
  local has_np="${5:-NO}"

  local expected_before="007_admin_ai_expert_v1"
  local expected_after="008_notification_center_v1"

  local count=0
  [[ "${has_n}" == "YES" ]] && count=$((count + 1))
  [[ "${has_nr}" == "YES" ]] && count=$((count + 1))
  [[ "${has_nd}" == "YES" ]] && count=$((count + 1))
  [[ "${has_np}" == "YES" ]] && count=$((count + 1))

  N008_OBJECTS_EXPECTED=4
  N008_OBJECT_PRESENT_COUNT="${count}"

  local none=NO all=NO some=NO
  if [[ "${count}" -eq 0 ]]; then
    none=YES
  elif [[ "${count}" -eq 4 ]]; then
    all=YES
  else
    some=YES
  fi

  CLEAN_PRE_008=NO
  PARTIAL_008=NO
  ALREADY_UPGRADED=NO
  INCONSISTENT_008=NO
  MIGRATION_PARTIAL_OR_INCONSISTENT=NO
  ALLOW_008_UPGRADE=NO
  SCHEMA_STATE=UNKNOWN

  if [[ "${rev}" == "${expected_before}" ]]; then
    if [[ "${none}" == "YES" ]]; then
      # State A: clean pre-008
      CLEAN_PRE_008=YES
      ALLOW_008_UPGRADE=YES
      SCHEMA_STATE=A_CLEAN_PRE_008
    else
      # State B: revision still 007 but some/all 008 tables exist
      PARTIAL_008=YES
      MIGRATION_PARTIAL_OR_INCONSISTENT=YES
      SCHEMA_STATE=B_PARTIAL_008
    fi
  elif [[ "${rev}" == "${expected_after}" ]]; then
    if [[ "${all}" == "YES" ]]; then
      # State C: fully upgraded
      ALREADY_UPGRADED=YES
      SCHEMA_STATE=C_ALREADY_008
    else
      # State D: stamped 008 but missing 008 objects
      INCONSISTENT_008=YES
      MIGRATION_PARTIAL_OR_INCONSISTENT=YES
      SCHEMA_STATE=D_INCONSISTENT
    fi
  else
    INCONSISTENT_008=YES
    MIGRATION_PARTIAL_OR_INCONSISTENT=YES
    SCHEMA_STATE=UNEXPECTED_REVISION
  fi
}
