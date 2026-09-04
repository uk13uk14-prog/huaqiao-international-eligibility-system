# GUOQIAO Notification Center V1 — Phase 3 Production Release

**Status:** PREPARED — awaiting M1 manual one-shot  
**PR:** #11 → `cursor/mobile-cloud-preview`  
**Agent auto-exec on M1:** **NO**

## Gate A — PR

| Item | Value |
| --- | --- |
| PR | #11 |
| Base | `cursor/mobile-cloud-preview` |
| Head | `cursor/notification-admin-mobile-v1-eee9` |
| CNber touched | NO |
| main touched | NO |
| Secrets invented | NO |
| Migration chain | `007_admin_ai_expert_v1` → `008_notification_center_v1` |

## Gate B — M1 script

`deploy/api/m1-notification-center-v1-production-release.sh`

Fail-closed. Production DB binding only:

- container=`huaqiao-postgres`
- host=`127.0.0.1`
- port=`5433`
- db=`huaqiao`
- user=from container `POSTGRES_USER`

Blocks: `:5432`, role guess `postgres`, SQLite, auto `pg_restore`, FCM/APNS/WebPush keys, CNber/main/tunnel/Caddy/secret changes.

## Expected fingerprint (abort if mismatch)

| Key | Expected |
| --- | --- |
| DB revision before | `007_admin_ai_expert_v1` |
| universities | 125 |
| admission_schedules | 900 |
| users | 2 |

Also snapshots: membership_plans / expert_consultations / eligibility_records / student_master_profiles / student_timeline_items.

## Backup

`pg_dump -Fc` → `~/guoqiao-backups/huaqiao_pre_008_*.dump`  
Must print `BACKUP_VERIFIED=YES` (`pg_restore -l`) before migrate.

## Apply 008

Uses `${BACKEND}/.venv/bin/python` only (never system python).  
`alembic upgrade 008_notification_center_v1`  
Expect `DB_REVISION_AFTER=008_notification_center_v1`.

On failure: stop, redact stderr, print revision, `ROLLBACK_REQUIRED=YES/NO`.  
No auto downgrade / no auto restore.

## Schema + integrity

Tables: `notifications`, `notification_rules`, `notification_devices`, `notification_preferences`  
`RULE_COUNT=27` (migration seed)  
Core business counts unchanged → `DATA_INTEGRITY=PASS`

## Reminder engine

1. **DRY RUN first** (default in release script): no send / no popup / no writes  
2. **ONE-SHOT only after confirm:**  
   `CONFIRM_NOTIFICATION_ONESHOT=YES bash deploy/api/m1-notification-center-v1-production-release.sh --reminder-oneshot`  
3. Second oneshot tick must show no new duplicates.

## Push status (unchanged)

- IN_APP=ENABLED  
- FCM_READY=NO  
- APNS_READY=NO  
- WEB_PUSH_READY=NO  

## Production freeze checklist (all required)

Freeze only when M1 stdout shows:

- DB_REVISION_AFTER=008_notification_center_v1  
- BACKUP_VERIFIED=YES  
- DATA_INTEGRITY=PASS  
- PUBLIC health + admin/notification APIs mounted  
- REMINDER_DRY_RUN=PASS  
- SCHEDULER_ONESHOT=PASS + SECOND_RUN_DUPLICATE_CREATED=0  
- Admin Mobile + Student H5 + AI→publish E2E PASS  

Otherwise `PRODUCTION_FREEZE=NO`.

## M1 one-shot command

See agent final reply: `M1_ONE_SHOT_COMMAND` — run manually, paste full stdout back.
