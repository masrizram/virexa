"""Platform adaptation engine (spec §33).

One canonical content item -> platform-native derivatives. Never blind cross-posting.
"""

PLATFORM_SPECS = {
    "youtube": {"title_max": 100, "description_max": 5000, "hashtags_max": 15},
    "instagram": {"caption_max": 2200, "hashtags_max": 30},
    "facebook": {"caption_max": 63206, "hashtags_max": 10},
    "tiktok": {"description_max": 2200, "hashtags_max": 10},
}


class PlatformConstraintError(Exception):
    pass


def _hashtags_for(platform, base_tags):
    spec = PLATFORM_SPECS.get(platform, {})
    limit = spec.get("hashtags_max", 10)
    tags = [t if t.startswith("#") else "#" + t for t in (base_tags or [])]
    return tags[:limit]


def _join_nonempty(parts):
    return "\n".join([x for x in parts if x])


def adapt_for_platform(platform, *, title, hook, description, cta, hashtags):
    """Build platform-native variant payload with constraint validation."""
    p = platform.lower()
    if p not in PLATFORM_SPECS:
        raise PlatformConstraintError("unsupported platform: " + platform)
    spec = PLATFORM_SPECS[p]
    tags = _hashtags_for(p, hashtags)

    base_title = (title or "").strip()
    base_desc = (description or "").strip()
    hook_text = (hook or "").strip()
    cta_text = (cta or "").strip()

    if p == "youtube":
        yt_title = base_title[: spec["title_max"]]
        yt_desc = _join_nonempty([hook_text, base_desc, cta_text])[: spec["description_max"]]
        return {
            "platform": p,
            "title": yt_title,
            "description": yt_desc,
            "keywords": [t.lstrip("#") for t in tags],
            "hashtags": tags,
            "cta": cta_text,
        }

    if p == "instagram":
        caption = _join_nonempty(
            [hook_text or base_title, base_desc, cta_text, " ".join(tags)]
        )[: spec["caption_max"]]
        return {
            "platform": p,
            "title": "",
            "description": caption,
            "hashtags": tags,
            "cta": cta_text,
        }

    if p == "facebook":
        discussion_hook = ("What do you think? " + (hook_text or base_title)).strip()
        caption = _join_nonempty(
            [base_title or hook_text, base_desc, discussion_hook, cta_text]
        )[: spec["caption_max"]]
        return {
            "platform": p,
            "title": "",
            "description": caption,
            "hashtags": tags,
            "cta": cta_text,
        }

    if p == "tiktok":
        desc = (hook_text or base_title)[: spec["description_max"]]
        if cta_text and len(desc) + len(cta_text) + 1 <= spec["description_max"]:
            desc = desc + " " + cta_text
        return {
            "platform": p,
            "title": "",
            "description": desc,
            "hashtags": tags,
            "cta": cta_text,
        }
