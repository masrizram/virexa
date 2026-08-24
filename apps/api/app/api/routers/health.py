"""Health / readiness endpoints (spec §49).

LIVENESS (/healthz) = process alive.
READINESS (/ready)  = dependencies usable (DB reachable).
DEPENDENCY HEALTH (/health/deps) = per-dependency status.
"""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.db.engine import get_engine

router = APIRouter()


@router.get("/healthz")
def liveness():
    return {"status": "ok"}


@router.get("/ready")
def readiness():
    checks = {}
    ok = True
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        ok = False
        checks["database"] = f"error: {type(exc).__name__}"
    return {"status": "ready" if ok else "not_ready", "checks": checks}


@router.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "env": settings.env,
        "dry_run": settings.dry_run,
        "autonomous_mode": settings.autonomous_mode,
        "ai_configured": settings.has_ai(),
    }
