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
# Production E2E (bearer auth; token is the SERVICE_TOKEN Fly secret)
API_BASE=https://virexa-api.fly.dev VIREXA_SERVICE_TOKEN=<token> bash scripts/e2e_dryrun.sh
fly status -a virexa-api && fly status -a virexa-windmill
curl -s https://virexa-api.fly.dev/health
```

## CI/CD (automatic)

- Push ke `main` → GitHub Actions `deploy` workflow: CI (pytest vs Postgres service) → deploy 5 app
  Fly paralel (api, windmill server, windmill worker, video, web) → verify smoke (`/healthz`, web, windmill).
- Token: 5 GitHub secret per-app `FLY_TOKEN_VIREXA_{API,WEB,WINDMILL,WINDMILL_WORKER,VIDEO}`
  (regenerate: `GH_TOKEN=... python scripts/set_gh_secret.py` — flyctl tokens create per app).
- CATATAN: `flyctl tokens create deploy --org <org>` TIDAK valid di flyctl v0.4.84 (output usage-error).
  Gunakan token per-app.

## Runtime evidence (2026-08-24, production)

- virexa-api.fly.dev: `/health` → `ai_configured:true, dry_run:true`; `/ready` → `database:ok` (Neon).
- E2E dry-run produksi: healthz ✓, safety round-trip ✓, discovery live HackerNews 5 item ✓, score 67.5 ✓.
- Windmill Fly: server + worker live; worker ping Neon db_latency 4-10ms.
- MPT (virexa-video.internal:8080): `/ping` 200 dari dalam network; `POST /api/v1/videos`
  **end-to-end SUKSES** (bukti 2026-08-24: task c3eceac5 → final-1.mp4 6.7MB + combined-1.mp4
  6.8MB + audio.mp3 + subtitle.srt). Key Pexels di-set via Fly secret `PEXELS_API_KEYS`
  (comma-separated untuk multi-key); entrypoint.py merge ENV → config.toml saat startup.
  Voice Azure format `en-US-AriaNeural` (voice UUID lama TIDAK valid di MPT versi baru).

## Known operational notes

- MPT API paths: `POST /api/v1/videos`, `GET /api/v1/tasks/{id}`, `GET /ping` (bukan /v1/*).
- MPT bind dual-stack `::` wajib agar reachable via Fly 6PN `.internal` (IPv6).
- Windmill Neon: perlu role `windmill_admin/user/password` cluster-wide + GRANT ke runtime role
  (migrasi Windmill merujuk ketiga role itu; bukti di infra/neon/00_bootstrap.sql).
- Windmill Fly default login admin@windmill.dev/changeme — **GANTI PASSWORD operator**.

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
