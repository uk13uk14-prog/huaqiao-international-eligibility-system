# Production Migration Readiness — 007_admin_ai_expert_v1

**Status:** PLAN ONLY — DO NOT EXECUTE ON M1 PRODUCTION IN THIS PHASE  
**PRODUCTION_DB_CHANGED=NO** (Phase 4)

## Scope

Additive Alembic revision `007_admin_ai_expert_v1` (`down_revision=006_student_profile_slots`):

| Change | Notes |
|--------|--------|
| `expert_consultations.student_id` | nullable + index + FK |
| `expert_consultations.assigned_consultant_id` | nullable + FK |
| `expert_consultations.ai_provider` | nullable |
| `expert_consultations.report_kind` | nullable |
| `expert_consultations.payload_json` | nullable |
| `eligibility_records.student_id` | nullable + index + FK — **no backfill** |
| `audit_events` | new table |

Already present (unchanged): `expert_consultations.ai_model`, `expert_consultations.status`, `consultation_report_versions`.

## Guarantees

- Does **not** require seed data
- Does **not** rewrite existing consultations / eligibility
- Existing consultation rows may keep `student_id NULL`
- Existing eligibility rows may keep `student_id NULL`
- No DROP of business data; downgrade only removes 007 additions

## Staging verification (already done)

- DB: `huaqiao_admin_staging` @ `127.0.0.1:5432` (NOT `:5433`)
- `UPGRADE / DOWNGRADE / REUPGRADE = PASS`
- Admin E2E draft→publish + isolation + audit + restart = PASS

## Production runbook (future ops window — NOT NOW)

### PRECHECK

1. Confirm branch contains `alembic/versions/007_admin_ai_expert_v1.py`
2. Confirm current production revision is `006_student_profile_slots`
3. Confirm no other open migrations ahead of 007
4. Confirm app code that *writes* `student_id` is deployed **with** or **after** schema (reads tolerate NULL)

### Backup

```bash
# On M1 ops host — example only
pg_dump -Fc -h 127.0.0.1 -p 5433 -U <user> -d huaqiao \
  -f ~/guoqiao-backups/huaqiao_pre_007_$(date +%Y%m%d_%H%M%S).dump
# backup verify: pg_restore -l <dump> | head
```

### Upgrade

```bash
export DATABASE_URL='postgresql+psycopg://...@127.0.0.1:5433/huaqiao'  # production URL
cd huaqiao-saas-pro/backend
alembic current   # expect 006_student_profile_slots
alembic upgrade 007_admin_ai_expert_v1
alembic current   # expect 007_admin_ai_expert_v1
```

### Schema verify

```sql
SELECT column_name FROM information_schema.columns
 WHERE table_name='expert_consultations'
   AND column_name IN ('student_id','assigned_consultant_id','ai_provider','report_kind','payload_json');
SELECT column_name FROM information_schema.columns
 WHERE table_name='eligibility_records' AND column_name='student_id';
SELECT to_regclass('public.audit_events');
```

### Data integrity

```sql
-- Old rows remain valid with NULL student_id
SELECT count(*) FILTER (WHERE student_id IS NULL) AS legacy_null,
       count(*) FILTER (WHERE student_id IS NOT NULL) AS bound
  FROM expert_consultations;
SELECT count(*) FILTER (WHERE student_id IS NULL) AS legacy_null
  FROM eligibility_records;
```

### Rollback (manual only)

Prefer restore from `pg_dump` if needed. Logical downgrade:

```bash
alembic downgrade 006_student_profile_slots
```

Note: downgrade drops `audit_events` and the new nullable columns — any Phase-3+ rows that relied on those columns lose that metadata.

## PRODUCTION_READY

**YES for schema safety** (additive, nullable, reversible, staging-proven).  
**NO for unattended production apply** until ops schedules backup window and explicitly approves M1 migration.
