# Production Migration Readiness — 010_student_crm_v1

**Status:** PLAN ONLY — DO NOT EXECUTE ON M1 PRODUCTION IN THIS PHASE  
**PRODUCTION_DB_CHANGED=NO**  
**PRODUCTION_MIGRATION_APPLIED=NO**  
**NAME_BACKFILL_APPLIED=NO**

## Scope

Additive Alembic revision `010_student_crm_v1` (`down_revision=009_csca_notification_rules`):

| Change | Notes |
|--------|--------|
| `student_master_profiles.assignee_user_id` | nullable FK → `users.id` (staff id, **not** name string) |
| `student_master_profiles.assigned_at` | nullable |
| `student_master_profiles.assigned_by_user_id` | nullable FK → `users.id` |
| `student_master_profiles.crm_stage` | default `UNASSIGNED` |
| `student_master_profiles.risk_level` | default `NONE` |
| `student_master_profiles.next_action` | text, default `''` |
| `student_master_profiles.next_follow_up_at` | nullable + index |
| `student_master_profiles.last_follow_up_at` | nullable |
| `student_master_profiles.identity_track` | default `''` |
| `student_follow_ups` | new table; rows keyed by `student_id` |

## Guarantees

- Does **not** mutate `universities` (125), `admission_schedules` (900)
- Does **not** mutate `notification_rules` (51 total / CSCA 24 / non-CSCA 27)
- Does **not** mutate CSCA 009 rules, eligibility, membership, user passwords
- Does **not** batch-rewrite student profile cipher blobs
- Assignee is always a `users.id` FK — never a display-name string
- Follow-ups are isolated by `student_id`
- Downgrade removes only 010 additions

## Staging verification (done)

- DB: `huaqiao_admin_staging` @ `127.0.0.1:5432` (**NOT** `:5433/huaqiao`)
- Cycle: `009 → 010 → 009 → 010` = **PASS**
- After cycle: revision `010_student_crm_v1`
- Notification inventory preserved: total=51, CSCA=24, non-CSCA=27
- Universities=125, timelines=900 (staging mirror)
- CRM / Student 360 / AI context E2E = **PASS**
- AI drafts only (`auto_send=false`); no raw cipher in AI context

## M1 name inspect (read-only, separate from migration)

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system
bash deploy/api/m1-student-name-backfill-inspect.sh --inspect-only
```

- Default `--inspect-only` — **no UPDATE**
- Decrypts profile only to resolve name source priority
- Never prints full cipher / passport / national id / password / JWT
- If no real name: `PROPOSED_DISPLAY_NAME=NONE`, UI shows `待补姓名`

## Production release script (NOT executed)

```bash
# After CRM code is on production tip AND human approval:
bash deploy/api/m1-student-crm-v2-production-release.sh
# Optional read-only diagnostic:
bash deploy/api/m1-student-crm-v2-production-release.sh --checkpoint-d-diagnostic-only
```

Safety mode (same as 007/008/009):

- expected before = `009_csca_notification_rules`
- expected after = `010_student_crm_v1`
- dynamic `PRE_USER_COUNT` / require `POST_USER_COUNT == PRE_USER_COUNT`
- universities=125, timelines=900
- notification rules=51 / CSCA=24 / non-CSCA=27 (must not regress)
- `pg_dump -Fc` + `pg_restore -l` verify
- block host `:5432`, block SQLite fallback
- correct `POSTGRES_USER` from container
- `.venv` python only
- fail closed
- **NO auto pg_restore**
- **NO name backfill APPLY**

## Production runbook (future ops window — NOT NOW)

### PRECHECK

1. Confirm production tip contains `alembic/versions/010_student_crm_v1.py` + CRM app code
2. Confirm current production revision is `009_csca_notification_rules`
3. Run name inspect (read-only) and keep dry-run proposals only
4. Confirm SaaS `:8010` / Caddy `:8088` / public API healthy

### Backup

Handled inside `m1-student-crm-v2-production-release.sh` (`pg_dump -Fc` + `pg_restore -l`).

### Upgrade

`009_csca_notification_rules` → `010_student_crm_v1` via bound `.venv` alembic.

### Post integrity

- `POST_USER_COUNT == PRE_USER_COUNT`
- universities=125, timelines=900
- notification rules=51 / CSCA=24 / non-CSCA=27
- CRM columns + `student_follow_ups` present

### Rollback

Prefer restore from verified dump (manual approve only). Logical downgrade:

```bash
alembic downgrade 009_csca_notification_rules
```

## PRODUCTION_READY

**YES for schema safety** (additive, reversible, staging-proven).  
**NO for unattended production apply** until ops schedules backup window and explicitly approves M1 migration.  
**NO name backfill apply** until inspect dry-run is reviewed.
