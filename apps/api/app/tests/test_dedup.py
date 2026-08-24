"""Dedup engine tests (spec §26)."""
from app.engines.dedup import dedup_hash, is_duplicate, jaccard, normalize_topic, token_set


def test_normalize():
    assert normalize_topic("AI Is Taking Over?! (2024)") == "ai is taking over 2024"


def test_exact_hash_deterministic():
    a = dedup_hash("Hello World", "rss", "x1")
    b = dedup_hash("Hello World", "rss", "x1")
    assert a == b
    c = dedup_hash("hello  world", "rss", "x1")  # same normalized
    assert a == c


def test_different_source_different_hash():
    assert dedup_hash("T", "rss", "1") != dedup_hash("T", "reddit", "1")


def test_jaccard_identical():
    assert jaccard(token_set("ai video tools"), token_set("ai video tools")) == 1.0


def test_jaccard_disjoint():
    assert jaccard(token_set("cat dog"), token_set("bird fish")) == 0.0


def test_near_duplicate_detection():
    recent = ["best ai video generator tools 2025", "how to grow on tiktok fast"]
    dup, sim, matched = is_duplicate("Best AI Video GENERATOR tools 2025!", recent)
    assert dup is True
    assert sim >= 0.82
    assert matched is not None


def test_not_duplicate():
    recent = ["best ai video generator tools 2025", "how to grow on tiktok fast"]
    dup, sim, _ = is_duplicate("quantum computing breakthrough explained", recent)
    assert dup is False
    assert sim < 0.82
