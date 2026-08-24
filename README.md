# Virexa — Autonomous Content Operating System

Fly.io (compute) · Neon PostgreSQL (state) · Windmill self-hosted (orchestration) · MoneyPrinterTurbo (video) · FastAPI (business) · Next.js (control center) · S3-compatible (media)

Status: **IN ACTIVE BUILD** — see `docs/` and FINAL REPORT section below for the verified state.

## Repository layout

```
virexa/
├── apps/
│   ├── api/                  # Python FastAPI backend (business domain)
│   │   ├── app/              # application code
│   │   └── alembic/          # migrations for content_os DB
│   └── control-center/       # Next.js + TypeScript control plane
├── flows/                    # Windmill TypeScript flows (sync via wmill CLI / API)
│   ├── content/              # f/content/*
│   ├── engagement/           # f/engagement/*
│   └── system/               # f/system/*
│   └── lib/                  # shared flow helper scripts
└── services/
    ├── windmill/             # Windmill server + worker Fly configs
    └── moneyprinterturbo/    # MoneyPrinterTurbo Fly config + overrides
└── infra/                    # fly.toml templates, neon SQL setup
└── scripts/                  # operational scripts (verify, e2e, deploy helpers)
└── docs/                     # architecture & operations documentation
```

## Documentation

- `docs/architecture.md` — topology, decisions, boundaries
- `docs/neon.md` — database layer, roles, pooling strategy
- `docs/windmill.md` — orchestration layer
- `docs/operations.md` — runbooks

## Development

Backend (Python 3.11+, uv):

```bash
cd apps/api
uv sync
uv run uvicorn app.main:app --reload
```

Control Center (Node 22+):

```bash
cd apps/control-center
npm install
npm run dev
```
