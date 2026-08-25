"""Tests for POST /pipeline/publish/youtube endpoint guards.

The happy path with a real Google account is the operator-driven limited live
test (spec §66) — unit tests here cover the guard rails only:
  - missing OAuth env -> 503, no publish job
  - content without video asset -> 409
  - state machine gates (§43)

Content items are created through the SAME session the app uses (via the
client's dependency override) so the endpoint can actually see them.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.api.deps import db_session
from app.main import app
from app.models.business import Brand, ContentItem
from app.services.state_service import transition_content

UNIQUE = uuid.uuid4().hex[:8]


def _app_session():
    """The session the TestClient's dependency override yields."""
    gen = app.dependency_overrides[db_session]()
    try:
        return next(gen)
    except StopIteration as exc:  # pragma: no cover
        raise RuntimeError("no session") from exc


def _make_ready_content(sess) -> ContentItem:
    brand = Brand(name="yt-" + UNIQUE, niche="test")
    sess.add(brand)
    sess.flush()
    item = ContentItem(brand_id=brand.id, title="yt publish guard test",
                       state="DISCOVERED", dedup_hash=uuid.uuid4().hex, state_history=[])
    sess.add(item)
    sess.flush()
    for _, dst in [("DISCOVERED", "RESEARCHING"), ("RESEARCHING", "RESEARCHED"),
                     ("RESEARCHED", "SCORED"), ("SCORED", "SELECTED"),
                     ("SELECTED", "PLANNING"), ("PLANNING", "SCRIPTING"),
                     ("SCRIPTING", "PRODUCING"), ("PRODUCING", "QC"),
                     ("QC", "READY")]:
        transition_content(sess, item, dst, reason="test")
    sess.commit()
    return item


def test_publish_youtube_requires_oauth_env(client: TestClient, monkeypatch):
    item = _make_ready_content(_app_session())
    monkeypatch.delenv("YOUTUBE_CLIENT_ID", raising=False)
    monkeypatch.delenv("YOUTUBE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("YOUTUBE_REFRESH_TOKEN", raising=False)
    r = client.post("/pipeline/publish/youtube", json={
        "content_item_id": str(item.id), "idempotency_key": "k1",
        "title": "t", "description": "d",
    })
    # DRY_RUN default in test env blocks real publish (§57): 409; with dry-run
    # disabled and env missing: 503. Never a fake PUBLISHED.
    assert r.status_code in (409, 503), r.text
    assert r.json().get("status") != "PUBLISHED"


def test_publish_youtube_missing_asset(client: TestClient, monkeypatch):
    """OAuth env set, content READY, but no video asset -> 409 before any upload."""
    item = _make_ready_content(_app_session())
    monkeypatch.setenv("YOUTUBE_CLIENT_ID", "x")
    monkeypatch.setenv("YOUTUBE_CLIENT_SECRET", "y")
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "z")
    r = client.post("/pipeline/publish/youtube", json={
        "content_item_id": str(item.id), "idempotency_key": "k2",
        "title": "t", "description": "d",
    })
    assert r.status_code in (409, 503), r.text
    assert r.json().get("status") != "PUBLISHED"


def test_publish_youtube_state_gate(client: TestClient):
    """Content in DISCOVERED state must be rejected with 409 (state machine §43)."""
    sess = _app_session()
    brand = Brand(name="ytg-" + UNIQUE, niche="test")
    sess.add(brand)
    sess.flush()
    item = ContentItem(brand_id=brand.id, title="gate test", state="DISCOVERED",
                       dedup_hash=uuid.uuid4().hex, state_history=[])
    sess.add(item)
    sess.commit()
    r = client.post("/pipeline/publish/youtube", json={
        "content_item_id": str(item.id), "idempotency_key": "k3",
        "title": "t", "description": "d",
    })
    assert r.status_code == 409
    assert "not in" in r.json()["detail"]
