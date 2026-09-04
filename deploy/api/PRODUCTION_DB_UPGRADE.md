# M1 Production Database Upgrade (003 → 006)

## Confirmed target

| Item | Value |
|------|-------|
| Container | `huaqiao-postgres` only |
| Database | `huaqiao` |
| URL (redacted) | `postgresql+psycopg://huaqiao:***@127.0.0.1:5433/huaqiao` |
| From revision | `003_r43_fix` |
| To revision | `006_student_profile_slots` |
| Path | 003 → 004 → 005 → 006 |

## ONE_SHOT (M1)

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system && \
git pull origin cursor/mobile-cloud-preview && \
bash deploy/api/m1-production-db-upgrade-recover.sh
```

## Checkpoint pipeline (FAIL CLOSED)

| CP | Action | Abort if |
|----|--------|----------|
| A | Identity: 125/900 + rev `003_r43_fix` | mismatch |
| B | `pg_dump -Fc` + `pg_restore -l` | backup invalid |
| C | Record pre counts | — |
| D | Create/verify `.env` (600), URL-encode password | wrong DB / not ignored |
| E | `.venv` + `import psycopg` | fail |
| F | Alembic chain 004/005/006 | diverge |
| G | `alembic upgrade head` | not on `006` |
| H | V2 tables/columns | missing |
| I | Post counts == pre (students may be 0) | drift |
| J | LaunchAgent `:8010` | health/students fail |
| K | `m1-go-live.sh` Caddy | health fail |
| L | `api.guoqiaoplan.com` tunnel | report only |

## Safety rules

- **SEED_ALLOWED=NO** — `.env` sets `GUOQIAO_SKIP_SEED=1`; `main.py` honors it (prevents schedule rewrite)
- **No invent** JWT/VAULT — recovered from known env files only; else CP J aborts after successful migration
- **No auto pg_restore** on failure — keep `~/guoqiao-backups/huaqiao_pre_006_*.dump`
- **CNBER/BETA untouched** — only `docker exec/cp` on `huaqiao-postgres`
- Never commit `.env` or dumps

## After abort on missing secrets

Migration may already be `006`. Add to `huaqiao-saas-pro/backend/.env`:

```env
JWT_SECRET_KEY=...
VAULT_FERNET_KEY=...
GUOQIAO_SKIP_SEED=1
```

Then:

```bash
launchctl kickstart -k "gui/$(id -u)/com.guoqiao.saas-backend"
# or re-run recover with .env already present (skips overwrite)
```
