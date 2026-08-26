"""Regression tests for the select-stage self-parity dedup bug (2026-08-26).

Before the fix, POST /pipeline/select with title == the opportunity's own topic
always returned DUPLICATE_TOPIC similarity=1.0 because recent_topics() included
the candidate opportunity itself among the dedup candidates.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select as sa_select

from app.api.routers import pipeline as pipeline_router
from app.engines import discovery as discovery_mod
from app.models.business import Opportunity
from app.services import pipeline_repo


def _seed_opp(client: TestClient, brand: str, topic: str) -> dict:
    """Create one opportunity through /pipeline/discover with a stubbed connector."""
    item = discovery_mod.DiscoveredItem(
        source="hackernews", source_id=uuid.uuid4().hex[:16], topic=topic,
        url="https://example.com/x",
        engagement={"points": 120},
    )

    def _fake(*_a, **_k):
        return discovery_mod.ConnectorResult(items=[item], errors=[])

    original = pipeline_router.discover_hackernews
    pipeline_router.discover_hackernews = _fake
    try:
        r = client.post(
            "/pipeline/discover",
            json={"brand": brand, "sources": ["hackernews"], "limit_per_source": 5},
        )
    finally:
        pipeline_router.discover_hackernews = original
    assert r.status_code == 200 and r.json()["created"] >= 1, r.text
    opps = client.get("/opportunities", params={"limit": 200}).json()
    mine = [o for o in opps if o["topic"] == topic]
    assert mine, f"seeded topic not found: {topic}"
    return mine[0]


@pytest.fixture()
def fresh_brand():
    return "selx-" + uuid.uuid4().hex[:8]


def _test_session(app) -> object:
    from app.api.deps import db_session

    override = app.dependency_overrides[db_session]
    return next(iter(override()), None)


def test_select_with_exact_topic_title_succeeds(client: TestClient, fresh_brand):
    """The natural API path: title == own topic must NOT be a duplicate of itself."""
    topic = f"Self parity regression {uuid.uuid4().hex[:8]}"
    opp = _seed_opp(client, fresh_brand, topic)
    r = client.post("/pipeline/select", json={"opportunity_id": opp["id"], "title": topic})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["selected"] is True, body
    assert body["content_item_id"]
    # The content item exists at state SELECTED after consolidation.
    cid = body["content_item_id"]
    got = client.get(f"/content/{cid}")
    assert got.status_code == 200, got.text
    assert got.json()["state"] == "SELECTED"


def test_cross_source_duplicate_still_blocked(client: TestClient, fresh_brand):
    """Sibling opportunities with identical stories block each other; a derived
    title passes once, then content history blocks reuse of that title."""
    story = f"Cross source dup story {uuid.uuid4().hex[:8]}"
    opp_a = _seed_opp(client, fresh_brand, story)
    opp_b = _seed_opp(client, fresh_brand, story)  # same topic text, separate row
    assert opp_a["id"] != opp_b["id"]

    # Selecting A with the raw story title is blocked — by its sibling B.
    r = client.post("/pipeline/select", json={"opportunity_id": opp_a["id"], "title": story})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["selected"] is False and body["reason"] == "DUPLICATE_TOPIC", body

    # A with a genuinely derived title goes through.
    derived = f"Deep dive: {story} explained simply"
    r2 = client.post("/pipeline/select", json={"opportunity_id": opp_a["id"], "title": derived})
    assert r2.status_code == 200, r2.text
    assert r2.json()["selected"] is True, r2.text

    # Reusing the derived title for B is blocked — by content history this time.
    r3 = client.post("/pipeline/select", json={"opportunity_id": opp_b["id"], "title": derived})
    assert r3.status_code == 200, r3.text
    body3 = r3.json()
    assert body3["selected"] is False and body3["reason"] == "DUPLICATE_TOPIC", body3


def test_repo_exclude_only_own_row(client: TestClient, fresh_brand):
    """Repo-level: excluding own id hides exactly that row; siblings stay visible."""
    topic = f"Repo exclude probe {uuid.uuid4().hex[:8]}"
    _seed_opp(client, fresh_brand, topic)
    _seed_opp(client, fresh_brand, topic)
    session = _test_session(client.app)
    rows = list(
        session.execute(sa_select(Opportunity).where(Opportunity.topic == topic)).scalars().all()
    )
    assert len(rows) == 2
    brand_id = rows[0].brand_id

    plain = pipeline_repo.recent_topics(session, brand_id)
    assert sum(1 for t in plain if t == topic) == 2

    excluded_a = pipeline_repo.recent_topics(session, brand_id, exclude_opportunity_id=rows[0].id)
    assert sum(1 for t in excluded_a if t == topic) == 1

    excluded_b = pipeline_repo.recent_topics(session, brand_id, exclude_opportunity_id=rows[1].id)
    assert sum(1 for t in excluded_b if t == topic) == 1


def test_content_history_dedup_unaffected():
    """Content-item titles keep blocking repeats regardless of opportunity exclusion."""
    from app.engines.dedup import is_duplicate

    sim = is_duplicate("Same Title", ["same title!"])
    assert sim[0] is True and sim[2] == "same title!"
