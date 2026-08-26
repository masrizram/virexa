"""Regression tests for publish idempotency on terminal states (2026-08-26).

A replayed idempotency key must return the recorded outcome of a terminal
publish job (PUBLISHED or DRY_RUN) with attempts untouched. FAILED remains
retryable by design (same key = retry).
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _mk_variant(client: TestClient) -> str:
    from app.api.deps import db_session

    override = client.app.dependency_overrides[db_session]
    sess = next(iter(override()), None)
    from app.models.business import PlatformVariant
    from app.services import pipeline_repo
    from app.services.state_service import transition_content

    brand = pipeline_repo.get_default_brand(sess, "idem-" + uuid.uuid4().hex[:8])
    content = pipeline_repo.create_content_item(sess, brand.id,
                                                title="Idem term " + uuid.uuid4().hex[:8])
    for st in ("RESEARCHING", "RESEARCHED", "SCORED", "SELECTED", "PLANNING", "SCRIPTING",
               "PRODUCING", "QC", "READY"):
        transition_content(sess, content, st)
    sess.flush()
    variant = PlatformVariant(content_item_id=content.id, platform="youtube", title="t",
                              description="d", hashtags=[], cta="", payload={})
    sess.add(variant)
    sess.flush()
    return str(variant.id)


def test_dry_run_key_replay_is_idempotent(client: TestClient):
    variant_id = _mk_variant(client)
    key = "term-" + uuid.uuid4().hex[:10]

    r1 = client.post("/pipeline/publish", json={
        "variant_id": variant_id, "idempotency_key": key, "status": "DRY_RUN"})
    assert r1.status_code == 200, r1.text
    first = r1.json()
    assert first["status"] == "DRY_RUN" and first["idempotent_reuse"] is False

    r2 = client.post("/pipeline/publish", json={
        "variant_id": variant_id, "idempotency_key": key, "status": "DRY_RUN"})
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["publish_job_id"] == first["publish_job_id"]
    assert body["idempotent_reuse"] is True, body
