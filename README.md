# PermitPulse v3

PermitPulse is a zero-human-ops STR compliance intelligence platform deployed as a single Vercel project:

- Next.js SSR frontend at repo root
- Django API served through Vercel Python functions (`api/index.py`)

## Repository layout

- `app/`: Next.js App Router frontend
- `api/index.py`: Vercel Python entrypoint (bridges to Django WSGI)
- `backend/`: Django domain logic, models, services, tests
- `vercel.json`: rewrites + daily cron definition

## API endpoints (unchanged)

- `POST /api/v1/address-checks`
- `GET /api/v1/address-checks/{check_id}`
- `POST /api/v1/portfolio/import`
- `GET /api/v1/cities/{city_code}/rules/latest`
- `GET /api/v1/alerts`
- `POST /api/v1/billing/checkout-session`
- `POST /api/v1/billing/webhook`
- `GET /api/v1/system/autonomy-status`
- `GET /api/v1/system/slo`

## New internal endpoint

- `POST /api/v1/internal/cron/daily-maintenance`
- `GET /api/v1/internal/cron/daily-maintenance` (used by Vercel Cron)

`DailyMaintenanceResult` response shape:

- `started_at`
- `finished_at`
- `cities_processed`
- `snapshots_published`
- `slo_metrics_count`
- `recovery_actions`
- `status`

## Local development

```bash
cp .env.example .env
python3 -m pip install -r backend/requirements.txt
npm install
```

- Frontend: `npm run dev`
- Backend tests: `cd backend && python3 manage.py test`

## CI/CD model

- GitHub Actions (`.github/workflows/ci.yml`) is validation-only.
- Deployment is handled by Vercel Git Integration:
  - Pull Requests -> Preview deployments
  - `main` -> Production deployment

## Vercel required environment variables

- `DJANGO_SECRET_KEY`
- `DATABASE_URL` (managed Postgres)
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_STARTER_PRICE_ID`
- `STRIPE_PRO_PRICE_ID`
- `STRIPE_TEAM_PRICE_ID`
- `OPENAI_API_KEY` (optional)
- `FRONTEND_ORIGIN`
- `NEXT_PUBLIC_API_BASE_URL`
- `CRON_SHARED_SECRET`

## Supabase connection

PermitPulse can run with Supabase as the primary Postgres:

- Set `SUPABASE_DB_URL` to your Supabase pooler connection string (recommended with `sslmode=require`).
- If `SUPABASE_DB_URL` is set, backend uses it before `DATABASE_URL`.
- Optional frontend client configuration:
  - `NEXT_PUBLIC_SUPABASE_URL`
  - `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Example Supabase DB URL:

```bash
postgresql://postgres.<project-ref>:<password>@aws-0-us-east-1.pooler.supabase.com:6543/postgres?sslmode=require
```

## Cron

`vercel.json` schedules one daily job on Hobby:

- `0 3 * * *` -> `/api/v1/internal/cron/daily-maintenance`

## Database migration policy

Migrations are intentionally not executed during deployment. Run them in a controlled step:

```bash
python backend/manage.py migrate
```
