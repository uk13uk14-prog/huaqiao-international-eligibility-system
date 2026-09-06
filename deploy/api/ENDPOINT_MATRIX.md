# Production H5 ↔ SaaS endpoint alignment (branch cursor/mobile-cloud-preview)

| Concern | H5 client | SaaS OpenAPI | Caddy acceptance |
|---------|-----------|--------------|------------------|
| Health | — | `GET /api/health` | same |
| Universities | `saasApi.universities` → `/api/universities` | `GET /api/universities` | same |
| Timeline (admission) | `saasApi.schedules` → `/api/schedules` | `GET /api/schedules` | same |
| Student list | `saasApi.students` → `/api/students` | `GET /api/students` | same (401/403 OK) |
| Student detail | `saasApi.student(id)` → `/api/students/{id}` | `GET /api/students/{id}` | — |
| Student meta | — | `GET /api/students/meta` | mount check (200) |
| Vault profile | `saasApi.vaultGet` → `/api/vault/profile` | `GET /api/vault/profile` | 401/403 OK |
| Auth | `saasApi.login` → `/api/auth/login` | `POST /api/auth/login` | 401 OK |
| History | `api.records` → `/api/records` | `GET /api/records` | 401/403 OK |
| Eligibility intl | `api.judgeInternational` → `/api/eligibility/international` | `POST ...` | 401/422 OK |
| Eligibility hq | `api.judgeHuaqiao` → `/api/eligibility/huaqiao` | `POST ...` | 401/422 OK |

Free-only (not on SaaS; not required for go-live): `/api/telemetry/session`, `/api/consultation`.

If `GET /api/students` returns **404** while OpenAPI lists it, restart the SaaS uvicorn process from current HEAD so `student_api` is loaded.
