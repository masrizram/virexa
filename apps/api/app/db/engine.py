"""Database engine/session management.

Neon strategy (spec §8):
- Runtime uses APP_DATABASE_URL (pooled endpoint via PgBouncer, transaction pooling).
- Migrations use APP_DATABASE_DIRECT_URL (direct, session semantics).
- pool_pre_ping so Neon suspend/resume doesn't poison the pool.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str | None = None, *, pooled: bool = True):
    settings = get_settings()
    u = url or (settings.app_database_url or settings.app_database_direct_url)
    if not u:
        raise RuntimeError("No database URL configured (APP_DATABASE_URL / APP_DATABASE_DIRECT_URL)")
    if pooled:
        return create_engine(u, pool_pre_ping=True, pool_size=10, max_overflow=20)
    return create_engine(u, pool_pre_ping=True, poolclass=NullPool)


def make_sessionmaker(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_engine = None
_session_factory: sessionmaker[Session] | None = None


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        _engine = make_engine(pooled=True)
        _session_factory = make_sessionmaker(_engine)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def reset_engine() -> None:
    """Test helper: dispose and forget the module-level engine."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def session_scope() -> Generator[Session, None, None]:
    """Transactional session scope; commit on success, rollback on error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def check_db_connection(engine) -> dict:
    """Readiness probe for Neon connectivity."""
    with engine.connect() as conn:
        server = conn.execute(text("SELECT version()")).scalar_one()
        db = conn.execute(text("SELECT current_database()")).scalar_one()
        user = conn.execute(text("SELECT current_user")).scalar_one()
    return {"ok": True, "server": server.split(",")[0], "database": db, "user": user}
