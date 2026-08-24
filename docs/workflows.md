# Workflows (Windmill flows ↔ Virexa API)

Principle (spec §19): **business logic lives in FastAPI; Windmill orchestrates only.**
Every flow script is a thin wrapper: call API → return result. Failures surface as
job failures in Windmill with full history; retries/schedules are Windmill's job.

## Flow inventory

| Flow path | File | API endpoint |
|---|---|---|
| `f/content/daily_cycle` | `flows/content/daily_cycle.ts` | orchestrates the stages below (order) |
| `f/content/discovery_daily` | `flows/content/discovery_daily.ts` | `POST /pipeline/discover` |
| `f/content/research_candidates` | `flows/content/research_candidates.ts` | `GET /opportunities` + dispatch |
| `f/system/health` | `flows/system/health.ts` | `GET /health`, `GET /ready` |

Stage API surface (all idempotent, all audited — see `app/api/routers/pipeline.py`):
`discover → research → score → select → strategy → script → produce → qc → adapt → publish-status`

## Deployment to Windmill

Sync via `wmill` CLI or the UI once Windmill is live on Fly:

```bash
wmill flow content/daily_cycle --code-file flows/content/daily_cycle.ts
# or bulk: wmill sync generate + wmill sync apply (workspace: admins → create 'virexa' workspace in prod)
```

Variables to set in Windmill (as workspace variables/resources, NOT in code):
- `VIREXA_API_BASE` = `http://virexa-api.internal:8000`
- `VIREXA_SERVICE_TOKEN` = service token secret

## Schedules (prod)

| Flow | Schedule (UTC) |
|---|---|
| `f/content/daily_cycle` | daily 01:00 |
| `f/content/discovery_daily` | every 4h |
| `f/system/health` | every 15m |

## Proven locally

Windmill script create + run-by-path + worker execution + result persistence:
see `docs/windmill.md` "Proof of execution" (job 119ms, result in Postgres).
