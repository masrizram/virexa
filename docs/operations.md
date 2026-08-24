# Operations Runbook

## Environment variables (formats only — values from Fly secrets / operator)

| Variable | Used by | Format |
|---|---|---|
| `APP_DATABASE_URL` | API runtime | `postgresql+psycopg://<role>:<pw>@<pooler-host>/content_os?sslmode=require` (pooled) |
| `APP_DATABASE_DIRECT_URL` | Alembic migrations | `postgresql+psycopg://<migrator>:<pw>@<direct-host>/content_os?sslmode=require` |
| `WINDMILL_DATABASE_URL` | Windmill server+worker | `postgres://windmill_runtime:<pw>@<host>/windmill?sslmode=require` |
| `OPENAI_COMPATIBLE_API_KEY` / `KIMI_API_KEY` / `GLM_API_KEY` | AI chain | provider API key |
| `AI_TASK_MODEL_*` | AI chain | `provider::model` per task class |
| `S3_ENDPOINT_URL` `S3_BUCKET` `S3_ACCESS_KEY_ID` `S3_SECRET_ACCESS_KEY` | media storage | S3-compatible creds |
| `MONEYPRINTER_BASE_URL` | video client | `http://virexa-video.internal:8080` (Fly) |
| `MONEYPRINTER_API_SECRET` | video client | shared secret |
| `VIREXA_SERVICE_TOKEN` | Windmill flows → API | bearer token |
| `DRY_RUN` | API | `true`/`false` |
| `AUTONOMOUS_MODE` | API | `true`/`false` (only after gates pass) |

Full secret list & provisioning order: `.env.example`.

## Neon bootstrap (operator, once)

1. Create Neon project (region near Fly `sin`).
2. Connect as project owner (direct connection string) and run:
   ```
   psql "$NEON_OWNER_DIRECT_URL" -f infra/neon/00_bootstrap.sql
   ```
   Creates databases `windmill` + `content_os`, roles `windmill_runtime`, `content_migrator`, `content_runtime`, `analytics_reader` (least privilege).
3. Windmill schema prep: `psql "$WINDMILL_DIRECT_URL" -f infra/neon/10_windmill_schema.sql`
4. Business DB grants: `psql "$CONTENT_OS_DIRECT_URL" -f infra/neon/20_content_os_grants.sql`

## Fly deployment (operator, in order)

```bash
# 1. API (business DB first)
cd apps/api
fly secrets set -a virexa-api APP_DATABASE_URL=... APP_DATABASE_DIRECT_URL=... DRY_RUN=true ...
fly deploy            # release command runs alembic upgrade head

# 2. Windmill (needs WINDMILL_DATABASE_URL secret first)
cd services/windmill
fly secrets set -a virexa-windmill WINDMILL_DATABASE_URL=...
fly deploy -c fly.server.toml
fly secrets set -a virexa-windmill-worker WINDMILL_DATABASE_URL=...
fly deploy -c fly.worker.toml

# 3. MoneyPrinterTurbo (internal only)
cd services/moneyprinterturbo
fly deploy    # no public port; reachable at virexa-video.internal:8080

# 4. Control Center
cd apps/control-center
fly deploy
```

## Daily verification

```bash
bash scripts/e2e_dryrun.sh                      # API pipeline (needs API_BASE)
WM=http://localhost:8001 bash scripts/windmill_smoke.sh   # local windmill
fly status -a virexa-api && fly status -a virexa-windmill
curl -s https://virexa-api.fly.dev/health/deps
```

## Recovery

- **API down**: Windmill jobs fail → they retry per schedule; state is in Neon, nothing lost. `fly restart -a virexa-api`.
- **Worker down**: jobs queue in Postgres; on worker restart they are claimed again (proven locally: job persisted + completed).
- **Machine restart**: no local disk state is authoritative (spec §47). Media → S3, state → Neon.
- **Emergency**: `POST /safety {"state": "EMERGENCY_STOP"}` — blocks publish/reply/DM immediately, monitoring retained.

## Local development

```bash
# Postgres for business DB (WSL docker)
docker run -d --name virexa-pg --restart unless-stopped -e POSTGRES_USER=virexa \
  -e POSTGRES_PASSWORD=virexa_dev -e POSTGRES_DB=content_os -p 55432:5432 postgres:16-alpine

# Windmill local stack
# see services/windmill/docker-compose.local.yml (or docker run commands in docs/windmill.md)

# API + tests
cd apps/api && uv sync
APP_DATABASE_URL=postgresql+psycopg://virexa:virexa_dev@<wsl-ip>:55432/content_os .venv/Scripts/python.exe -m pytest

# Control Center
cd apps/control-center && npm install && npm run dev
```
