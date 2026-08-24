"""Deduplication engine (spec §26 memory / dedup step).

Strategy: normalized-text simhash-style hash + exact hash match first,
then token Jaccard similarity against recent items for near-duplicate detection.
No external embedding dependency in the mandatory path (provider-independent);
similarity is lexical and deterministic.
"""
from __future__ import annotations

import hashlib
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def normalize_topic(topic: str) -> str:
    return " ".join(_TOKEN_RE.findall(topic.lower()))


def dedup_hash(topic: str, source: str = "", source_id: str = "") -> str:
    """Exact-duplicate hash. source+source_id included when present so the same
    story from the same source collides, but cross-source near-dup detection
    uses topic_hash only."""
    basis = normalize_topic(topic) if not source else f"{source}:{source_id}:{normalize_topic(topic)}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def topic_hash(topic: str) -> str:
    return hashlib.sha256(normalize_topic(topic).encode("utf-8")).hexdigest()


def token_set(topic: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(topic.lower()))


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def is_duplicate(
    topic: str,
    recent_topics: list[str],
    *,
    threshold: float = 0.82,
) -> tuple[bool, float, str | None]:
    """Check topic against recent topics.

    Returns (is_dup, similarity, matched_topic). similarity is the max Jaccard.
    """
    target = token_set(topic)
    best_sim = 0.0
    best_topic: str | None = None
    for candidate in recent_topics:
        sim = jaccard(target, token_set(candidate))
        if sim > best_sim:
            best_sim = sim
            best_topic = candidate
    return (best_sim >= threshold, round(best_sim, 4), best_topic if best_sim >= threshold else None)
