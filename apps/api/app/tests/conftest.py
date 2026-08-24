"""Shared test fixtures. Requires a running Postgres (dev container)."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Default: local dev container (WSL docker). CI/staging can override via env.
DEFAULT_URL = "postgresql+psycopg://virexa:virexa_dev@172.17.81.243:55432/content_os"

os.environ.setdefault("APP_DATABASE_URL", os.environ.get("APP_DATABASE_TEST_URL", DEFAULT_URL))
os.environ.setdefault("DRY_RUN", "true")

from app.db.engine import Base, make_engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def db_engine():
    url = os.environ["APP_DATABASE_URL"]
    engine = make_engine(url, pooled=False)
    # Tests must NEVER drop the shared dev schema (spec: no destructive runtime
    # schema mutation). Create tables idempotently; teardown leaves schema intact.
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(db_engine):
    """Per-test transactional session: rollback everything after each test."""
    connection = db_engine.connect()
    trans = connection.begin()
    from sqlalchemy.orm import Session

    sess = Session(bind=connection, expire_on_commit=False)
    yield sess
    sess.close()
    trans.rollback()
    connection.close()


@pytest.fixture()
def client(db_engine):
    """TestClient with DB session overridden to the transactional test session."""
    from app.api.deps import db_session

    connection = db_engine.connect()
    trans = connection.begin()
    from sqlalchemy.orm import Session

    sess = Session(bind=connection, expire_on_commit=False)

    def override():
        yield sess

    app.dependency_overrides[db_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    sess.close()
    trans.rollback()
    connection.close()
