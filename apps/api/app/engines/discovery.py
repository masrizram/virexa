"""Discovery connectors (spec §23).

A single connector failure must not terminate all discovery — each connector
returns (items, errors) and the orchestrator aggregates.
"""
from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

import feedparser
import httpx


@dataclass
class DiscoveredItem:
    source: str
    source_id: str
    topic: str
    url: str = ""
    published_at: datetime | None = None
    engagement: dict = field(default_factory=dict)
    trend: dict = field(default_factory=dict)
    raw_metadata: dict = field(default_factory=dict)


@dataclass
class ConnectorResult:
    items: list = field(default_factory=list)
    errors: list = field(default_factory=list)


def normalize_topic(topic: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else " " for c in topic)
    return " ".join(cleaned.split())


def make_source_id(source: str, unique_part: str) -> str:
    return hashlib.sha256(f"{source}:{unique_part}".encode()).hexdigest()[:40]


def _ts_to_utc(ts) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (OverflowError, ValueError, TypeError):
        return None


def discover_rss(feed_urls: list, *, timeout: float = 15.0) -> ConnectorResult:
    result = ConnectorResult()
    for url in feed_urls:
        try:
            resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                             headers={"User-Agent": "virexa-discovery/0.1"})
            resp.raise_for_status()
            parsed = feedparser.parse(resp.content)
            for entry in parsed.entries[:20]:
                published = None
                st = getattr(entry, "published_parsed", None)
                if st:
                    try:
                        published = datetime.fromtimestamp(calendar.timegm(st), tz=UTC)
                    except (OverflowError, ValueError):
                        published = None
                entry_id = getattr(entry, "id", None) or entry.get("link", "")
                result.items.append(DiscoveredItem(
                    source="rss",
                    source_id=make_source_id("rss", entry_id),
                    topic=entry.get("title", ""),
                    url=entry.get("link", ""),
                    published_at=published,
                    raw_metadata={"feed": url},
                ))
        except Exception as exc:
            result.errors.append(f"rss:{url}:{type(exc).__name__}:{exc}")
    return result


def discover_hackernews(*, limit: int = 30, timeout: float = 15.0) -> ConnectorResult:
    result = ConnectorResult()
    try:
        resp = httpx.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=timeout)
        resp.raise_for_status()
        ids = resp.json()[:limit]
        for item_id in ids:
            try:
                item = httpx.get(
                    f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                    timeout=timeout,
                ).json()
                if not item or item.get("type") != "story" or not item.get("title"):
                    continue
                result.items.append(DiscoveredItem(
                    source="hackernews",
                    source_id=make_source_id("hackernews", str(item_id)),
                    topic=item["title"],
                    url=item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                    published_at=_ts_to_utc(item.get("time")),
                    engagement={"score": item.get("score", 0),
                                "comments": item.get("descendants", 0)},
                    trend={"velocity": min(100.0, float(item.get("score", 0)) / 3.0)},
                ))
            except Exception as exc:
                result.errors.append(f"hackernews:item:{item_id}:{type(exc).__name__}")
    except Exception as exc:
        result.errors.append(f"hackernews:top:{type(exc).__name__}:{exc}")
    return result


def discover_reddit(subreddits: list, *, limit_per_sub: int = 25,
                    timeout: float = 15.0) -> ConnectorResult:
    result = ConnectorResult()
    headers = {"User-Agent": "virexa-discovery/0.1 (content research)"}
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/top.json?t=day&limit={limit_per_sub}"
        try:
            resp = httpx.get(url, timeout=timeout, headers=headers, follow_redirects=True)
            if resp.status_code != 200:
                result.errors.append(f"reddit:{sub}:HTTP {resp.status_code}")
                continue
            data = resp.json()
            for child in data.get("data", {}).get("children", []):
                d = child.get("data", {})
                if not d.get("title"):
                    continue
                result.items.append(DiscoveredItem(
                    source="reddit",
                    source_id=make_source_id("reddit", d.get("id", "")),
                    topic=d["title"],
                    url="https://www.reddit.com" + (d.get("permalink", "") or ""),
                    published_at=_ts_to_utc(d.get("created_utc")),
                    engagement={"score": d.get("score", 0),
                                "comments": d.get("num_comments", 0),
                                "upvote_ratio": d.get("upvote_ratio")},
                    trend={"velocity": min(100.0, float(d.get("score", 0)) / 20.0)},
                ))
        except Exception as exc:
            result.errors.append(f"reddit:{sub}:{type(exc).__name__}:{exc}")
    return result
