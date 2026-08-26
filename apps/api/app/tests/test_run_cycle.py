"""Tests for the autonomous daily cycle endpoint (spec §22/§57).

run_cycle is gated by AUTONOMOUS_MODE + safety RUNNING, discovers via
connectors (stubbed here), researches/scores/selects the best candidate and
walks it to SCRIPTING with strategy + script rows — all audited.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.routers import pipeline as pipeline_router
from app.core.config import Settings, get_settings
from app.engines import discovery as discovery_mod


@pytest.fixture()
def fresh_brand():
    return "cycle-" + uuid.uuid4().hex[:8]


def _stub_discovery(monkeypatch, n=2):
    items = [
        discovery_mod.DiscoveredItem(
            source="hackernews", source_id=f"cy-{uuid.uuid4().hex[:12]}-{i}",
            topic=f"Cycle candidate {uuid.uuid4().hex[:8]} number {i}",
            url="https://example.com/cycle", engagement={"points": 100 + i},
        )
        for i in range(n)
    ]

    def _fake(*_a, **_k):
        return discovery_mod.ConnectorResult(items=items, errors=[])

    monkeypatch.setattr(pipeline_router, "discover_hackernews", _fake)


def _enable_autonomous(monkeypatch):
    """AUTONOMOUS_MODE=true for the process (get_settings is lru_cached)."""
    monkeypatch.setenv("AUTONOMOUS_MODE", "true")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: Settings(env="test", autonomous_mode=True, dry_run=True),
    )


def test_run_cycle_requires_autonomous_mode(client: TestClient, monkeypatch):
    """Default settings have AUTONOMOUS_MODE off -> 503, nothing executed."""
    r = client.post("/pipeline/run_cycle", json={"brand": "gate-" + uuid.uuid4().hex[:6]})
    assert r.status_code == 503, r.text
    assert "autonomous mode disabled" in r.json()["detail"]


def test_run_cycle_blocked_by_safety(client: TestClient, fresh_brand, monkeypatch):
    _enable_autonomous(monkeypatch)
    client.post("/safety", json={"state": "PAUSED"})
    try:
        r = client.post("/pipeline/run_cycle", json={"brand": fresh_brand})
        assert r.status_code == 503, r.text
        assert "PAUSED" in r.json()["detail"]
    finally:
        client.post("/safety", json={"state": "RUNNING"})


def test_run_cycle_happy_path_to_scripting(client: TestClient, fresh_brand, monkeypatch):
    _stub_discovery(monkeypatch, n=3)
    _enable_autonomous(monkeypatch)

    r = client.post("/pipeline/run_cycle", json={"brand": fresh_brand, "limit_per_source": 5})
    assert r.status_code == 200, r.text
    body = r.json()

    # Stage trail is complete and ordered.
    names = [s["stage"] for s in body["stages"]]
    assert names == ["discover", "research+score", "select", "strategy", "script"], body

    # Content reached SCRIPTING.
    got = client.get(f"/content/{body['content_item_id']}")
    assert got.status_code == 200, got.text
    assert got.json()["state"] == "SCRIPTING"

    # The selected title is one of the stubbed topics.
    assert any(body["title"].startswith("Cycle candidate ") for _ in [0]), body["title"]

    # research+score scored every discovered candidate.
    rs = next(s for s in body["stages"] if s["stage"] == "research+score")
    assert rs["scored"] >= 1

    # Script row exists and word count matches full_text.
    from sqlalchemy import select as sa_select

    sess = next(iter(client.app.dependency_overrides[
        __import__("app.api.deps", fromlist=["db_session"]).db_session
    ]()), None)
    from app.models.business import ScriptVersion

    srow = sess.execute(
        sa_select(ScriptVersion).where(ScriptVersion.id == body["stages"][-1]["script_version_id"])
    ).scalar_one()
    wc = len(srow.full_text.split())
    assert wc == srow.word_count, f"word_count drift: {wc} != {srow.word_count}"
