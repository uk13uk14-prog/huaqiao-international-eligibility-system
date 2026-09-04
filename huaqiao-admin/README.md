# huaqiao-admin

国侨升学运营 / 顾问后台（Admin + AI Expert Console V1）

- Stack: Vue 3 + Vite + Element Plus
- Target domain: `https://admin.guoqiaoplan.com`（本轮仅 scaffold / staging-dev，不部署生产）
- Auth: SaaS JWT（`role=admin` → console `super_admin`）；不使用 Free `ADMIN_TOKEN`
- API: `/api/admin/v1/*` on SaaS backend (`:8010`)

```bash
npm install
npm run dev   # http://127.0.0.1:5190
```

Demo login (seed): `admin@example.com` / `admin123456`
