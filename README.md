# Virexa — Autonomous Content Operating System

Fly.io (compute) · Neon PostgreSQL (state) · Windmill self-hosted (orchestration) ·
MoneyPrinterTurbo (video) · FastAPI (business) · Next.js (control center) · S3 (media).

## Status

| Area | State |
|---|---|
| FastAPI business core (28 tables, state machine, 7 engines, AI chain, MPT client) | ✅ 47/47 tests |
| Alembic migration on real Postgres | ✅ 29 tables verified |
| Live E2E dry-run (discovery from Hacker News, scoring, safety toggle) | ✅ PASS=3 FAIL=0 |
| Windmill server + worker + Postgres (local, prod topology) | ✅ job executed & persisted |
| Control Center Next.js | ✅ build PASS |
| Fly configs (api/web/windmill/worker/video) + Neon bootstrap SQL + CI | ✅ ready |
| Fly deploy + Neon provisioning | ⏸ operator credentials required (see below) |

## Layout

```
apps/api                 FastAPI business core (uv, pytest, alembic)
apps/control-center      Next.js dashboard
flows/                   Windmill flow scripts (thin API wrappers)
services/windmill        fly.server.toml, fly.worker.toml, local compose
services/moneyprinterturbo  Dockerfile + fly.toml (internal)
infra/neon               bootstrap SQL (DBs, roles, grants)
scripts/                 e2e_dryrun.sh, windmill_smoke.sh
docs/                    architecture, operations, windmill, workflows
```

## Quick start (local)

```bash
# business DB
wsl docker run -d --name virexa-pg --restart unless-stopped \
  -e POSTGRES_USER=virexa -e POSTGRES_PASSWORD=virexa_dev -e POSTGRES_DB=content_os \
  -p 55432:5432 postgres:16-alpine

cd apps/api
uv sync
export APP_DATABASE_URL='postgresql+psycopg://virexa:virexa_dev@<WSL-IP>:55432/content_os'
export APP_DATABASE_DIRECT_URL="$APP_DATABASE_URL"
PYTHONPATH= PYTHONHOME= .venv/Scripts/python.exe -m alembic upgrade head
PYTHONPATH= PYTHONHOME= .venv/Scripts/python.exe -m pytest        # 47 tests
```

Windmill local + smoke: `docs/windmill.md`. Deployment: `docs/operations.md`.

## Operator blockers (spec §62)

| Blocker | Needed for | Unblock |
|---|---|---|
| Neon project + connection strings | staging+prod DBs | create project, run `infra/neon/*.sql`, set Fly secrets |
| AI provider API key(s) | research/script/strategy generation | set `OPENAI_COMPATIBLE_API_KEY` etc. |
| S3-compatible storage creds | media persistence | set `S3_*` secrets |
| Social platform OAuth apps | publishing/engagement | create developer apps, OAuth consent |
| Fly deploy approval | all 5 apps | `fly deploy` per docs/operations.md order |

DRY_RUN defaults to true everywhere; no public side effect can occur until the
operator explicitly disables it AND `AUTONOMOUS_MODE` gates pass (spec §57, §67).
