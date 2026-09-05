# M1 Production Database Source Recovery

## Status

| Step | Script | Writes `.env`? | Starts backend? | Mutates DB? |
|------|--------|----------------|-----------------|-------------|
| **Discover** | `m1-db-source-discover.sh` | NO | NO | NO (SELECT only) |
| **Schema fingerprint** | `m1-db-schema-fingerprint.sh` | NO | NO | NO (SELECT only) |
| **Guard** | `production-db-guard.sh` | NO | NO | NO |
| **Restore `.env`** | *(not yet — next phase only if IDENTITY=YES)* | YES (future) | NO | NO |
| **Runtime recover** | `m1-saas-runtime-recover.sh` | NO | YES (after guard PASS) | blocked until `.env` OK |
| **Migration** | *(future, after backup)* | NO | NO | **FORBIDDEN until approved** |

## Critical distinction

| Flag | Meaning |
|------|---------|
| `DATABASE_IDENTITY_CONFIRMED` | This is the real prod DB (125 universities, 900 schedules, core SaaS tables). **Does not require** `student_master_profiles`. |
| `SCHEMA_CURRENT` | DB has Student Profile V2 tables (`student_master_profiles` + `student_timeline_items`). |
| `STUDENT_TABLE_PRESENT` | `student_master_profiles` exists (alembic ≥ `004_student_master_profile`). |

Example (current M1 evidence):

```text
DATABASE_IDENTITY_CONFIRMED=YES   # 125/900/users/core tables
SCHEMA_CURRENT=NO                 # pre-V2; no student_master_profiles
STUDENT_TABLE_PRESENT=NO
```

Do **not** discard the database because V2 student tables are absent.

## Known M1 facts (from discovery)

- Container: `huaqiao-postgres` (`postgres:16`, volume `huaqiao_pgdata`, restart `unless-stopped`)
- Host: `127.0.0.1:5433` → `5432`
- Database: `huaqiao` · User: `huaqiao`
- Fingerprint: universities=125, admission_schedules=900, users=2, membership_plans=7
- `student_master_profiles` **absent** → schema predates Student Profile V2
- Historical “2 students” likely = `USER_COUNT=2` and/or legacy `customer_vaults` — **not** V2 rows
- `backend/.env` missing — **do not create empty SQLite**

## Alembic map (repo)

| Revision | Creates / changes |
|----------|-------------------|
| `001_initial` | Core SaaS + **`customer_vaults`** (legacy profile storage) |
| `002_privacy` | Privacy columns |
| `003_r43_fix` | users.permissions, eligibility privacy |
| **`004_student_master_profile`** | **`CREATE student_master_profiles`** |
| **`005_student_timeline`** | **`CREATE student_timeline_items`** |
| `006_student_profile_slots` | status/archive columns + seat override |

Runtime helper after 004 exists: `migrate_vault_if_needed()` (vault → V2). **Do not run migrations in this phase.**

## ONE_SHOT — schema fingerprint (M1)

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system && \
git pull origin cursor/mobile-cloud-preview && \
bash deploy/api/m1-db-schema-fingerprint.sh
```

Reads `alembic_version`, COUNT-only legacy sources, prints `DATABASE_URL_REDACTED` (password never shown).

## Future backup rule (not executed now)

Before any production `alembic upgrade`:

1. `pg_dump` database `huaqiao` (timestamped)
2. Verify backup non-zero
3. Only then consider migration

## Production DB guard

```bash
bash deploy/api/production-db-guard.sh huaqiao-saas-pro/backend
```

No `DATABASE_URL` / `.env` → **FAIL** (no empty sqlite).

## Safety

- SELECT / `information_schema` / COUNT only via `docker exec … psql`
- No password / PII / `SELECT *`
- No stash pop, no seed, no CNber/main edits
