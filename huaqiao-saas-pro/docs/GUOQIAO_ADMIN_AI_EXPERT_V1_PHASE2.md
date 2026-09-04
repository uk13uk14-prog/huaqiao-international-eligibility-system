# GUOQIAO Admin + AI Expert Console V1 — Phase 2

See also: `GUOQIAO_ADMIN_AI_EXPERT_V1_AUDIT_REPORT.md`

## Delivered

- `huaqiao-admin/` Vue3 scaffold (desktop-first)
- `/api/admin/v1/*` Student 360 + AI Expert DRAFT workspace
- RBAC proposal (`super_admin`/`consultant`/`support`); V1 maps `admin` → `super_admin`
- Eligibility legacy mapping with `UNRESOLVED` for multi-student owners
- Alembic draft (NOT APPLIED): `backend/alembic/drafts/007_admin_ai_expert_v1_NOT_APPLIED.py`
- Tests: `backend/tests/test_admin_v1.py`

## Explicit non-goals this round

Production deploy / DB migration / Cloudflare / Tunnel / Caddy / secrets / main merge / CNber
