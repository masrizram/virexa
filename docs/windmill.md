# Windmill Self-Hosted on Fly.io

## Verified architecture (local proof, mirrors prod topology)

| Component | Container | Status |
|---|---|---|
| Postgres (windmill DB) | `virexa-wm-pg` (postgres:16-alpine) | ✅ running |
| Windmill server | `virexa-wm-server` (ghcr.io/windmill-labs/windmill:main) | ✅ `server started on port=8000`, migrations applied |
| Windmill worker | `virexa-wm-worker` (same image, MODE=worker) | ✅ `workers_alive=1`, db_latency 2-7ms |

## Proof of execution (spec §64 runtime validation)

1. Login `POST /api/auth/login` (default admin@windmill.dev/changeme — **change in prod**) → token.
2. Script create: `POST /api/w/{workspace}/scripts/create` — required fields: `path`, `summary`, `language` (`deno` for TS), `content`.
   - Workspace created on first login is **`admins`** (not `windmill`).
3. Run by path: `POST /api/w/{workspace}/jobs/run/p/{path}` with `{}` body → job id.
4. Job `01a0338c-30db-446c-c8b6-69eb7c8458eb` → **Completed in 119ms**, result `{"ok":true,"ran":1787571220861}` persisted in `v2_job_completed` (Postgres). Worker claim + completion + persistence all verified.

## Neon migration notes (PHASE 3 follow-up on real Neon)

Windmill runs its own sqlx migrations at startup (`_sqlx_migrations` table) — the runtime role must be able to CREATE/ALTER tables in its schema. On Neon:
- Use a dedicated `windmill` database, role `windmill_runtime` with `CREATE` on schema public (bootstrap SQL handles grants).
- **Connection mode**: verify with runtime evidence per spec §8. Local proof used direct connections; for Neon start with the **pooled** endpoint only if job claim latency stays healthy — otherwise switch `WINDMILL_DATABASE_URL` to direct. Windmill uses LISTEN/NOTIFY-style polling on Postgres; if Neon PgBouncer transaction mode interferes with sessions, use direct (documented decision, test first on staging).
- Neon has no true superuser; Windmill only needs DB-owner-level privileges inside its own database, which Neon grants to the database owner. Compatible (schema runs as owner).

## Worker groups (prod)

`fly.worker.toml` deploys `WORKER_GROUP=general`. For media-heavy work later, add a second worker app (e.g. `virexa-windmill-worker-media`) with `WORKER_GROUP=media` + larger machine, and tag MPT jobs with that group (spec §15).

## Env

| Var | Value |
|---|---|
| `DATABASE_URL` | Neon windmill DB (secret) |
| `MODE` | `server` / `worker` |
| `NUM_WORKERS` | concurrency per machine (default 2 locally) |
| `WORKER_GROUP` | `general` (extendable) |
