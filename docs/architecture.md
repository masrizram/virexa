# Virexa Architecture

## Topology (spec §2)

```
                         INTERNET
                            │
                ┌───────────▼────────────┐
                │    FLY.IO EDGE         │
                └───────────┬────────────┘
                            │
        ┌───────────────────┼─────────────────────┐
        ▼                   ▼                     ▼
 virexa-web (Next.js)  virexa-api (FastAPI)  virexa-windmill (server)
        │                   │                     │
        │                   │                     ▼
        │                   │              Neon: windmill DB
        │                   ▼                     ▲
        │              Neon: content_os           │
        │                                         │
        │              virexa-windmill-worker ────┤ (same DB, no direct server link)
        │                   │
        │                   ▼ (Fly private net: virexa-video.internal:8080)
        │              virexa-video (MoneyPrinterTurbo)
        │                   │
        │                   ▼
        └────────── S3-compatible object storage
```

## Responsibility boundaries (spec §71)

| Layer | Owns | Never does |
|---|---|---|
| Fly.io | compute (Machines) | state |
| Neon | persistence (2 DBs: windmill, content_os) | compute |
| Windmill | orchestration, scheduling, retries, job history | business logic |
| FastAPI | business domain, state machine, QC, scoring, policies | scheduling |
| MoneyPrinterTurbo | video rendering | persistence (temp only) |
| S3 | media bytes | metadata |
| Next.js | human control plane | DB credentials |

## Key decisions

1. **Separate Fly Apps** for web/api/windmill/worker/video → independent deploy & scaling (§3).
2. **No Redis/Celery/queue** — Windmill's Postgres-backed job system is the only queue (§6).
3. **Neon two-database split** with least-privilege roles (§7, §9, §10).
4. **Pooled vs direct Neon**: runtime uses pooled URL; Alembic migrations use direct URL (§8).
5. **Fly Volumes**: none by default; media persists in S3, state in Neon (§17).
6. **Idempotent publishing** via (variant_id, idempotency_key) unique constraint (§44).
7. **Safety states** RUNNING/PAUSED/EMERGENCY_STOP gate every external side effect (§53).
8. **DRY_RUN** blocks publish/reply/DM while allowing research+generation (§57).

## Local development

- API: `apps/api` (uv, `.venv`) — tests run against Postgres container `virexa-pg` (port 55432 via WSL IP).
- Windmill local: `docker run` containers virexa-wm-pg / virexa-wm-server (:8001) / virexa-wm-worker — see `services/windmill/docker-compose.local.yml`.
- Control Center: `apps/control-center` (npm run dev).

## Naming (Fly apps)

| App | Service | Public |
|---|---|---|
| virexa-web | Next.js control center | yes |
| virexa-api | FastAPI | yes |
| virexa-windmill | Windmill server | yes (auth) |
| virexa-windmill-worker | Windmill worker | no |
| virexa-video | MoneyPrinterTurbo | no (internal :8080) |
