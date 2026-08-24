"""FastAPI application factory."""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import (
    content,
    health,
    opportunities,
    pipeline,
    reviews,
    safety,
)
from app.api.routers import (
    settings as settings_router,
)
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Virexa Content OS API",
        version="0.1.0",
        docs_url=None if settings.env == "production" else "/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.env != "production" else [],
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def service_auth(request: Request, call_next):
        """Service token auth: required in staging/production; /health* and /ready* stay open."""
        if settings.env in ("staging", "production") and settings.service_token:
            path = request.url.path
            is_open = path.startswith("/health") or path.startswith("/ready")
            header = request.headers.get("authorization", "")
            supplied = header.removeprefix("Bearer ").strip()
            if not is_open and supplied != settings.service_token:
                return JSONResponse(status_code=401, content={"detail": "unauthorized"})
        return await call_next(request)

    app.include_router(health.router)
    app.include_router(opportunities.router)
    app.include_router(content.router)
    app.include_router(pipeline.router)
    app.include_router(reviews.router)
    app.include_router(safety.router)
    app.include_router(settings_router.router)
    return app


app = create_app()
