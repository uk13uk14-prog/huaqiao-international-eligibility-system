# M1 Production Database Source Recovery

## Status

| Step | Script | Writes `.env`? | Starts backend? | Mutates DB? |
|------|--------|----------------|-----------------|-------------|
| **Discover** | `deploy/api/m1-db-source-discover.sh` | NO | NO | NO (SELECT only) |
| **Guard** | `deploy/api/production-db-guard.sh` | NO | NO | NO |
| **Restore `.env`** | *(not yet — next phase only if confirmed)* | YES (future) | NO | NO |
| **Runtime recover** | `m1-saas-runtime-recover.sh` | NO | YES (after guard PASS) | app startup may seed — **blocked until `.env` OK** |

## Known M1 facts

- Container: `huaqiao-postgres`
- Host port: `127.0.0.1:5433` → container `5432`
- Historical fingerprint: universities≈125, admission_schedules≈900, student_master_profiles≈2
- `huaqiao-saas-pro/backend/.env` currently missing
- No local `saas_pro.db` — **do not create empty SQLite**

## ORM tables (SaaS)

See `huaqiao-saas-pro/backend/app/models.py`:

- `universities`, `admission_schedules` (catalog/timeline in DB; also code catalog in `university_catalog.py` → may be MIXED)
- `student_master_profiles` (students — **DB only**)
- `users`, `tenants`, `eligibility_records`, `membership_plans`, …

## ONE_SHOT discovery (M1)

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system && \
git pull origin cursor/mobile-cloud-preview && \
bash deploy/api/m1-db-source-discover.sh
```

Paste the `SUMMARY` block back. Only if `DATABASE_SOURCE_CONFIRMED=YES` will a **separate** restore script be allowed to write `backend/.env`.

## Production DB guard

```bash
bash deploy/api/production-db-guard.sh huaqiao-saas-pro/backend
```

- No `DATABASE_URL` / `.env` → **FAIL** (no sqlite create)
- `sqlite:///` → only PASS if file already exists and is non-trivial size
- `postgresql://…` → PASS (URL redacted in output)

Wired into:

- `m1-saas-backend-run.sh`
- `m1-saas-runtime-recover.sh`

## Safety

- Discovery: SELECT / `\l` / `\dt` / `information_schema` only via `docker exec … psql`
- Passwords / full `DATABASE_URL` never printed (always `***` / `REDACTED`)
- No `stash pop`, no alembic, no seed, no CNber/main edits
