# PermitPulse v3 Execution Checklist (Vercel Single Project)

- [x] Move Next.js app from `frontend/` to repository root
- [x] Add Vercel Python bridge (`api/index.py`) for Django API routing
- [x] Add `vercel.json` rewrites and daily cron schedule
- [x] Add internal cron endpoint with auth and maintenance response schema
- [x] Remove Celery/Redis runtime dependency from deployment path
- [x] Keep GitHub Actions as CI-only workflow
- [x] Remove legacy script-based deploy workflows
- [x] Update documentation for Vercel Git Integration + env vars + migration policy
- [x] Validate backend tests and frontend lint/build
