# Phase 5 Production Release — status

## Done from Cloud Agent

- PR #6 squash-merged → `cursor/mobile-cloud-preview` (`e1f365a`)
- Secret scan PASS; pytest admin v1 PASS (10)
- Admin build with `VITE_ADMIN_API_BASE=https://api.guoqiaoplan.com`
- Cloudflare Worker `guoqiao-admin` deployed
  - workers.dev: https://guoqiao-admin.rambolluk.workers.dev (200)
  - custom domain registered: `admin.guoqiaoplan.com` (CF Workers Domains enabled; DNS may lag local resolvers)

## Must run on M1

```bash
cd /Users/agent001/deploy/huaqiao-international-eligibility-system
git pull origin cursor/mobile-cloud-preview
bash deploy/api/m1-admin-ai-expert-v1-production-release.sh
```

Then:
1. Confirm admin login (need `users.role=admin`)
2. Create test student via H5 if profiles=0
3. Admin AI Draft→Publish E2E
4. H5 「专家规划」 shows PUBLISHED only
5. Redeploy/refresh H5 worker if needed so app has Phase 4 UI
6. Set PRODUCTION_FREEZE=YES only after all PASS

## Not done by Cloud Agent

- M1 backup / alembic upgrade 007 (no M1 SSH)
- SaaS restart on M1
- Production E2E against live DB
