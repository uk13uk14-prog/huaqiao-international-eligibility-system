# GUOQIAO Admin + AI Expert Console V1 — Phase 3

## Delivered

- Staging admin runtime: `VITE_ADMIN_API_BASE` + `.env.example` (port 5190)
- Frozen `/api/admin/v1` contract including `ai-drafts` persistence routes
- DB-persisted DRAFT → REVIEWED → APPROVED → PUBLISHED on `expert_consultations` + versions
- `GET /api/students/{id}/published-consultations` (owner, PUBLISHED only)
- Durable `audit_events` model + writer (metadata scrubbed)
- Migration draft 007 reviewed (nullable adds only; **NOT APPLIED**)
- Privacy-minimized AI context (no passport/ID/cert numbers)

## Explicit non-goals

Production deploy / production DB migration / Cloudflare / Tunnel / Caddy / secrets / main / CNber
