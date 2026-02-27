# Autonomy Contract

## Non-stop execution

The platform only considers itself complete when configured SLO and business conditions are met.

## No-human-ops invariants

- No manual approval gates in ingestion/publishing.
- No manual deployment approvals in default flow (Vercel Git integration drives releases).
- No manual incident triage in default recovery path.
- No manual first-pass billing response for known payment events.

## Safety defaults

- `AUTO_CONSERVATIVE` decision mode is used when confidence is below threshold.
- Last known good snapshot remains active when parsing/validation fails.
- Daily maintenance endpoint is protected by `CRON_SHARED_SECRET` or Vercel cron header.

## Schedule policy (Vercel Hobby)

- Data and ops maintenance runs once daily via Vercel Cron.
- Cron path: `/api/v1/internal/cron/daily-maintenance`.

## Auditability

- Every autonomous action is persisted in `AutonomyEvent`.
- Every rollback is persisted in `RollbackEvent`.
- Every policy decision is persisted in `CustomerPolicyAction`.
