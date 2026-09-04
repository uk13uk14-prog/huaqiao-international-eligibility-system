# GUOQIAO Admin + AI Expert Console V1 — Phase 5 Production Report

**As of:** 2026-09-04 (Cloud Agent re-verify)  
**Target branch:** `cursor/mobile-cloud-preview` @ `cb07df3`  
**PRODUCTION_FREEZE:** NO (M1 DB migrate + SaaS restart + E2E pending)

---

## CHECKPOINT A — PR MERGE — PASS

| Field | Value |
|-------|-------|
| PR_MERGED | YES (#6) |
| MERGE_COMMIT | `e1f365a28d76349969e39378b271ba49ebfdc4d5` |
| TARGET_BRANCH | `cursor/mobile-cloud-preview` |
| MAIN_CHANGED | NO |
| Follow-up | PR #7 squash-merged → `cb07df3` (M1 release script + admin Worker config) |

Migration in tree: `huaqiao-saas-pro/backend/alembic/versions/007_admin_ai_expert_v1.py`  
Secret scan: no production `.env` / dump / credentials in merge.

---

## CHECKPOINT H–I — ADMIN BUILD / DEPLOY — PASS (Cloud)

| Field | Value |
|-------|-------|
| ADMIN_BUILD | PASS (`VITE_ADMIN_API_BASE=https://api.guoqiaoplan.com`) |
| ADMIN_DEPLOY | PASS Worker `guoqiao-admin` |
| ADMIN_URL | https://admin.guoqiaoplan.com → **200** (public DNS A @ 1.1.1.1 / 8.8.8.8) |
| Fallback | https://guoqiao-admin.rambolluk.workers.dev → **200** |
| Bundle API base | `https://api.guoqiaoplan.com` only (no localhost / private IP / Tailscale as API target) |
| Workers Domain | `admin.guoqiaoplan.com` → service `guoqiao-admin`, enabled=true |
| H5 「专家规划」 | Deployed (bundle contains `专家规划` + `published-consultations`) |
| Tunnel / Caddy | NOT changed from Cloud Agent |

---

## CHECKPOINT B–G — M1 PRODUCTION DB / SAAS — BLOCKED

Cloud Agent **cannot** SSH to M1 (`/Users/agent001/deploy/...` absent).  
**Self-hosted workers:** 0 connected.

Live production API probe (2026-09-04):

| Probe | Result |
|-------|--------|
| `GET https://api.guoqiaoplan.com/api/health` | **200** |
| OpenAPI `/api/admin/v1/*` | **0 paths** |
| `GET /api/admin/v1/dashboard` | **404** |
| Legacy `/api/admin/stats` (pre-v1) | 401 (exists) |

⇒ Production SaaS process has **not** pulled `cursor/mobile-cloud-preview` + restarted after Admin V1 merge.  
⇒ DB revision almost certainly still **`006_student_profile_slots`** (cannot confirm without M1).

### ONE_SHOT (must run on M1)

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system
git pull origin cursor/mobile-cloud-preview
bash deploy/api/m1-admin-ai-expert-v1-production-release.sh
```

Script covers: precheck (125/900/users=2, SaaS:8010, Caddy:8088, tunnel LaunchAgent) →  
`pg_dump -Fc` → `pg_restore -l` verify → alembic **006→007** → schema/integrity → CORS add `admin.guoqiaoplan.com` → `launchctl kickstart` SaaS.  
**Does not** auto `pg_restore`, merge `main`, touch CNber/tunnel/Caddy routes, or silent-SQL promote admin.

---

## CHECKPOINT J–N — ADMIN / H5 E2E / FREEZE — PENDING

Blocked until M1 script PASS and `/api/admin/v1` appears on production.

Then on M1 / manually:

1. Confirm `CURRENT_DB_REVISION=007_admin_ai_expert_v1` + data integrity (125/900/users=2).
2. If `users.role=admin` count = 0 → **do not** silent SQL; owner confirms email → controlled promote.
3. If `student_master_profiles=0` → create test student via H5 (own test account), then Admin Student 360.
4. AI: Generate → DRAFT → Edit → REVIEWED → Approve → APPROVED → Publish → PUBLISHED; audit + versions.
5. H5 login as that student → 「专家规划」 shows **PUBLISHED only**.
6. Privacy: passport/id masked; no raw cipher in admin UI / AI context.
7. Only then: `PRODUCTION_FREEZE=YES`.

---

## CI repair (2026-09-04 follow-up)

Pre-existing CI reds on `cursor/mobile-cloud-preview` (via open PR → main):

| Check | Root cause | Fix |
|-------|------------|-----|
| alembic-check | `postgresql+psycopg://` without `psycopg` package; free `003` down_revision mismatch; DB `huaqiao_free` missing | install `psycopg[binary]`; create DBs; fix `003` → `002_privacy`; also verify saas **007** |
| backend-tests | no `pytest` / `httpx` installed | pip install in CI |
| Deploy H5 | missing repo secret `CLOUDFLARE_API_TOKEN` | soft-warn (build still verified); manual/cloud deploy OK |
| Workers Builds (CF) | Cloudflare Git build integration | out of band / secrets — not blocking M1 |

---

## Absolute safety (still in force)

| Guard | Status |
|-------|--------|
| MAIN_CHANGED | NO |
| TUNNEL_CHANGED | NO |
| CADDY_CHANGED | NO |
| SECRET_CHANGED | NO |
| CNBER_CHANGED | NO |
| Auto pg_restore | NO |
| student_id backfill guessing | NO |
| PRODUCTION_DB_CHANGED | NO (Cloud Agent) |

---

## USER_ACTION_REQUIRED

**YES — run M1 ONE_SHOT above**, then reply with script stdout (BACKUP_FILE, DB_REVISION_AFTER, ADMIN_USER_COUNT) so Cloud Agent can continue Admin/H5 E2E probes and freeze.

Rollback path (manual only): report `~/guoqiao-backups/huaqiao_pre_007_*.dump` — do not auto restore.
