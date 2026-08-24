"""YouTube adapter tests — mock transport, no network (spec §34: capabilities
are explicit; unsupported ops raise UnsupportedCapability, never fake success).
"""
from __future__ import annotations

import httpx
import pytest

from app.platforms.base import UnsupportedCapability
from app.platforms.youtube import YouTubeAdapter


def make_adapter(handler) -> YouTubeAdapter:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    return YouTubeAdapter("test-token", http=http)


def test_publish_video_unlisted_default():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        if request.url.path.startswith("/upload/youtube/v3/videos"):
            seen["auth"] = request.headers.get("Authorization", "")
            import json
            body = json.loads(request.content.decode())
            seen["privacy"] = body["status"]["privacyStatus"]
            seen["title"] = body["snippet"]["title"]
            return httpx.Response(200, headers={"Location": "https://upload/session/1"})
        if request.url.path == "/session/1" and request.method == "PUT":
            seen["bytes"] = len(request.content)
            return httpx.Response(201, json={"id": "vid123"})
        return httpx.Response(404)

    ad = make_adapter(handler)
    res = ad.publish_video({
        "video_path": __file__,  # reuse this test file as bytes source
        "title": "Proof of upload",
        "description": "desc",
    })
    assert res["platform_post_id"] == "vid123"
    assert res["remote_url"] == "https://www.youtube.com/watch?v=vid123"
    assert res["status"] == "PUBLISHED"
    assert seen["privacy"] == "unlisted"  # §66: smallest safe publication
    assert seen["title"] == "Proof of upload"
    # Bearer token is presented on the API init call (session PUT is pre-authorized)
    assert seen["auth"] == "Bearer test-token"
    assert seen["bytes"] > 0


def test_publish_privacy_override_public_allowed():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/upload/youtube/v3/videos"):
            return httpx.Response(200, headers={"Location": "https://upload/session/2"})
        return httpx.Response(201, json={"id": "vid456"})

    ad = make_adapter(handler)
    res = ad.publish_video({"video_bytes": b"x" * 16, "title": "T",
                            "privacy_status": "public"})
    assert res["privacy_status"] == "public"


def test_delete_post():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "videos/delete" in str(request.url)
        assert "vid123" in str(request.url)
        return httpx.Response(204)

    ad = make_adapter(handler)
    assert ad.delete_post("vid123")["deleted"] is True


def test_get_metrics():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "part=statistics" in str(request.url)
        return httpx.Response(200, json={"items": [{
            "id": "vid123",
            "statistics": {"viewCount": "12", "likeCount": "3", "commentCount": "1"},
            "contentDetails": {"duration": "PT30S"},
        }]})

    ad = make_adapter(handler)
    m = ad.get_metrics("vid123")
    assert m["views"] == 12 and m["likes"] == 3 and m["comments"] == 1
    assert m["duration"] == "PT30S"


def test_unsupported_capabilities_raise():
    ad = make_adapter(lambda r: httpx.Response(200))
    for fn in (lambda: ad.schedule_post({}, "2026-01-01T00:00:00Z"),
               lambda: ad.read_comments("v"),
               lambda: ad.reply_comment("v", "c", "hi"),
               lambda: ad.read_messages(),
               lambda: ad.reply_message("c", "hi")):
        with pytest.raises(UnsupportedCapability):
            fn()


def test_publish_init_failure_raises_with_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/upload/youtube/v3/videos"):
            return httpx.Response(403, json={"error": {"message": "quota exceeded"}})
        return httpx.Response(404)

    from app.platforms.youtube import YouTubeError
    ad = make_adapter(handler)
    with pytest.raises(YouTubeError) as ei:
        ad.publish_video({"video_bytes": b"x" * 10, "title": "T"})
    assert ei.value.status == 403
    assert ei.value.reason == "UPLOAD_INIT_FAILED"
