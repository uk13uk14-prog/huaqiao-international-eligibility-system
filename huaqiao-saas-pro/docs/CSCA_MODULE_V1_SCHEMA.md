# CSCA Exam Module V1 — Schema Proposal (Staging)

## Summary

CSCA (China Scholastic Competency Assessment) student data is stored as an
**encrypted Master Profile JSON section** `profile.csca`.

- **No production SQL column migration required** for profile fields.
- Optional staging migration `009_csca_notification_rules` only seeds
  notification rules (additive). **Do not production-apply in this turn.**

## Profile section: `csca`

| Field | Type | Notes |
|-------|------|-------|
| `csca_status` | enum | `NOT_PLANNED` \| `PLANNED` \| `REGISTERED` \| `TAKEN` \| `RESULT_AVAILABLE` |
| `csca_exam_date` | ISO date or `""` | Real dates only |
| `csca_registration_deadline` | ISO date or `""` | Real dates only |
| `csca_result_date` | ISO date or `""` | Real dates only |
| `csca_score` | string | Optional |
| `csca_level` | string | Optional |
| `csca_notes` | string | Optional |
| `registration_deadline_source` | `student`\|`admin`\|`official`\|`""` | Provenance |
| `exam_date_source` | same | Provenance |
| `result_date_source` | same | Provenance |
| `updated_at` | ISO datetime | |

## Date safety

- Missing / invalid / placeholder → UI shows **待官方公布**
- **FAKE_DATE_ALLOWED = NO**
- Timeline + notification generation only when a real ISO date exists
- Sources allowed: official data, admin entry, student explicit entry

## Timeline nodes (when status is PLANNED / REGISTERED + real dates)

| Title | Marker |
|-------|--------|
| CSCA报名截止 | `[csca:registration_deadline]` |
| CSCA考试 | `[csca:exam_date]` |
| CSCA成绩发布 | `[csca:result_date]` |

## Notification event types

- `CSCA_REGISTRATION_DEADLINE`
- `CSCA_EXAM_DATE`
- `CSCA_RESULT_DATE`
- `CSCA_PREPARATION`

Reminder ladder: T-30 / T-14 / T-7 / T-3 / T-1 / T-0 (only with real dates).

## Planning / university context

Expose `csca_status` + `csca_score` for future planning reads.
**Do not** hardcode “university X requires CSCA” in this phase.

## Auth / trial

CSCA uses existing login + trial/paid access. No new membership gate.

## Migration

| Item | Value |
|------|-------|
| Schema change required | Profile JSON only (no SQL columns) |
| Staging migration | `009_csca_notification_rules` (notification rule seed) |
| Production migration applied | **NO** |
