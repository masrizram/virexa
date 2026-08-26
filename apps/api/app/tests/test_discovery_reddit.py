"""Reddit discovery resilience: RSS fallback + 429 pacing/retry (26 Aug prod).

Evidence that drove these tests: on Fly sin egress reddit .json is hard-blocked
(403), and back-to-back requests to .rss get HTTP 429 with an empty body.
"""
import xml.etree.ElementTree as ET

import httpx
import pytest

from app.engines.discovery import (
    _REDDIT_MIN_INTERVAL,
    _reddit_get,
    discover_reddit,
    make_source_id,
)


ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Test Post About AI</title>
    <link href="https://www.reddit.com/r/artificial/comments/abc123/test_post/" />
    <updated>2026-08-25T22:00:00Z</updated>
  </entry>
</feed>"""


def _resp(status: int, text: str = "") -> httpx.Response:
    return httpx.Response(status, text=text)


@pytest.fixture
def paced(monkeypatch):
    """No real sleeps; record intervals instead."""
    sleeps: list[float] = []
    monkeypatch.setattr("app.engines.discovery.time.sleep", sleeps.append)
    return sleeps


def test_rss_fallback_collects_items_when_json_403(monkeypatch, paced):
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "/top.json?" in url:
            return _resp(403, "<html>blocked</html>")
        assert url.endswith("/top/.rss")
        return _resp(200, ATOM)

    monkeypatch.setattr("app.engines.discovery.httpx.get", fake_get)
    result = discover_reddit(["artificial"], limit_per_sub=10)

    assert result.errors == []
    assert len(result.items) == 1
    item = result.items[0]
    assert item.source == "reddit"
    assert item.topic == "Test Post About AI"
    assert item.source_id == make_source_id("reddit", "abc123")
    # RSS exposes no scores — engagement stays empty, never faked
    assert item.engagement == {}


def test_429_burst_still_fails_reports_both_jalur(monkeypatch, paced):
    def fake_get(url, **kwargs):
        return _resp(403) if "/top.json?" in url else _resp(429)

    monkeypatch.setattr("app.engines.discovery.httpx.get", fake_get)
    result = discover_reddit(["artificial"])

    assert result.items == []
    assert result.errors == ["reddit:artificial:HTTP 403 and .rss fallback failed"]


def test_reddit_get_retries_429_then_succeeds(monkeypatch, paced):
    responses = iter([_resp(429), _resp(429), _resp(200, "ok")])
    monkeypatch.setattr(
        "app.engines.discovery.httpx.get", lambda url, **kw: next(responses))

    resp = _reddit_get("https://www.reddit.com/r/x/top/.rss",
                       headers={}, timeout=5)

    assert resp.status_code == 200
    # linear backoff after each 429: 1x then 2x the min interval
    assert paced == [_REDDIT_MIN_INTERVAL, _REDDIT_MIN_INTERVAL * 2]


def test_reddit_get_gives_up_after_retry_budget(monkeypatch, paced):
    monkeypatch.setattr(
        "app.engines.discovery.httpx.get",
        lambda url, **kw: _resp(429))

    resp = _reddit_get("https://www.reddit.com/r/x/top/.rss",
                       headers={}, timeout=5)

    assert resp is not None and resp.status_code == 429


def test_requests_are_paced_between_subreddits(monkeypatch, paced):
    def fake_get(url, **kwargs):
        return _resp(200, ATOM if url.endswith(".rss") else '{"data":{"children":[]}}')

    monkeypatch.setattr("app.engines.discovery.httpx.get", fake_get)
    discover_reddit(["technology", "artificial"])

    # one pacing sleep per subreddit request burst (json attempt per sub);
    # internal 429 retries add none here because no 429 occurred
    assert paced == [_REDDIT_MIN_INTERVAL, _REDDIT_MIN_INTERVAL]


def test_rss_malformed_xml_returns_none_not_crash(monkeypatch, paced):
    def fake_get(url, **kwargs):
        return _resp(403) if "/top.json?" in url else _resp(200, "<not-atom")

    monkeypatch.setattr("app.engines.discovery.httpx.get", fake_get)
    result = discover_reddit(["artificial"])

    assert result.items == []
    assert result.errors == ["reddit:artificial:HTTP 403 and .rss fallback failed"]
