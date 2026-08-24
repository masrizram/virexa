"""Platform adaptation tests (spec §33)."""
import pytest

from app.engines.adaptation import adapt_for_platform


def test_youtube_variant():
    v = adapt_for_platform(
        "youtube", title="T" * 150, hook="Hook line", description="Desc", cta="Subscribe",
        hashtags=["ai", "viral"],
    )
    assert len(v["title"]) <= 100
    assert "Subscribe" in v["description"]
    assert v["keywords"] == ["ai", "viral"]
    assert v["hashtags"] == ["#ai", "#viral"]


def test_instagram_caption_with_tags():
    v = adapt_for_platform(
        "instagram", title="T", hook="H", description="D", cta="Follow", hashtags=["a", "b"]
    )
    assert "#a #b" in v["description"]
    assert v["title"] == ""


def test_tiktok_hook_first():
    v = adapt_for_platform("tiktok", title="T", hook="Wait for it", description="D",
                           cta="Follow", hashtags=["fyp"])
    assert v["description"].startswith("Wait for it")
    assert "#fyp" in v["hashtags"]


def test_facebook_discussion_hook():
    v = adapt_for_platform("facebook", title="News", hook="H", description="D", cta="Comment",
                           hashtags=[])
    assert "What do you think?" in v["description"]


def test_unsupported_platform_raises():
    with pytest.raises(Exception):
        adapt_for_platform("myspace", title="T", hook="H", description="D", cta="C", hashtags=[])


def test_hashtag_limit_youtube_15():
    tags = [f"t{i}" for i in range(30)]
    v = adapt_for_platform("youtube", title="T", hook="H", description="D", cta="C", hashtags=tags)
    assert len(v["hashtags"]) == 15
