# GUOQIAO Admin + AI Expert Console V1 — Phase 4

## Staging

- DB: `huaqiao_admin_staging` @ `127.0.0.1:5432`
- Migration promoted: `alembic/versions/007_admin_ai_expert_v1.py`
- Scripts:
  - `backend/scripts/staging_migrate_007.sh`
  - `backend/scripts/staging_admin_e2e.py`

## H5

- Member center section「专家规划」reads `GET /api/students/{id}/published-consultations`
- Only PUBLISHED; no provider/model/admin notes

## Production

- See `PRODUCTION_MIGRATION_007_READINESS.md` — **do not apply on M1 in this phase**
