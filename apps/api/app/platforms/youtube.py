"""YouTube adapter — official Data API v3, OAuth installed-app flow (spec §34/§35).

Capabilities (verified against YouTube Data API v3):
  publish_video  — resumable upload, default privacyStatus=unlisted (spec §66
                   limited live test: smallest safe real publication)
  delete_post    — videos.delete (rollback path for live tests)
  get_metrics    — videos.getRating/statistics via videos.list (part=statistics)

Explicitly unsupported (never faked):
  schedule_post / read_comments / reply_comment / read_messages / reply_message
  (commentThreads endpoints exist but are not wired yet — do not pretend).

Tokens: access + refresh tokens are passed in by the caller; this adapter never
stores credentials. The caller keeps refresh tokens in the secret store
(Fly secrets) per spec — platform_connections.token_ref points at the secret name.
"""
from __future__ import annotations

from pathlib import Path

import httpx

from app.platforms.base import Capabilities, UnsupportedCapability

YOUTUBE_UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos"
YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3/"
YOUTUBE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Scopes required for upload + read stats + delete own uploads.
OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]

UPLOAD_TIMEOUT = httpx.Timeout(60.0, read=600.0)


class YouTubeError(Exception):
    """YouTube API error with HTTP status and reason, never swallowed."""

    def __init__(self, message: str, status: int = 0, reason: str = ""):
        super().__init__(message)
        self.status = status
        self.reason = reason


class YouTubeAdapter:
    platform = "youtube"
    capabilities = Capabilities(
        publish_video=True,
        schedule_post=False,
        read_comments=False,
        reply_comment=False,
        read_messages=False,
        reply_message=False,
        get_metrics=True,
        delete_post=True,
    )

    def __init__(self, access_token: str, *, client: httpx.Client | None = None,
                 http: httpx.Client | None = None):
        self._token = access_token
        self._http = client or http or httpx.Client(timeout=UPLOAD_TIMEOUT)

    # ------------------------------------------------------------------ auth
    @staticmethod
    def refresh_access_token(refresh_token: str, client_id: str, client_secret: str,
                             http: httpx.Client | None = None) -> dict:
        """Exchange refresh token for a fresh access token (OAuth installed-app)."""
        h = http or httpx.Client(timeout=30.0)
        resp = h.post(YOUTUBE_TOKEN_URL, data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        })
        if resp.status_code != 200:
            raise YouTubeError(
                f"token refresh failed: {resp.status_code} {resp.text[:200]}",
                status=resp.status_code, reason="TOKEN_REFRESH_FAILED")
        data = resp.json()
        return {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 3600),
            "scope": data.get("scope", ""),
        }

    # --------------------------------------------------------------- publish
    def publish_video(self, payload: dict) -> dict:
        """Resumable upload. payload:
            video_path (str, required)  — local file OR bytes via video_bytes
            title (str, required)
            description (str)
            tags (list[str])
            privacy_status (str) — unlisted(default)/private/public per §66
            category_id (str)    — default 22 (People & Blogs)
        Returns {platform_post_id, remote_url, status}.
        """
        title = payload.get("title") or "Untitled"
        meta = {
            "snippet": {
                "title": title[:100],
                "description": (payload.get("description") or "")[:5000],
                "tags": [str(t)[:100] for t in (payload.get("tags") or [])[:30]],
                "categoryId": str(payload.get("category_id") or "22"),
            },
            "status": {
                "privacyStatus": payload.get("privacy_status") or "unlisted",
                "selfDeclaredMadeForKids": False,
            },
        }
        headers = {
            "Authorization": "Bearer " + self._token,
            "Content-Type": "application/json; charset=UTF-8",
        }
        # Step 1: initiate resumable session
        init = self._http.post(
            YOUTUBE_UPLOAD_URL + "?uploadType=resumable&part=snippet,status",
            json=meta, headers=headers)
        if init.status_code != 200:
            raise YouTubeError(
                f"upload init failed: {init.status_code} {init.text[:300]}",
                status=init.status_code, reason="UPLOAD_INIT_FAILED")
        session_url = init.headers.get("Location")
        if not session_url:
            raise YouTubeError("upload init returned no session URL",
                               reason="UPLOAD_INIT_FAILED")

        # Step 2: PUT the bytes
        data = payload.get("video_bytes")
        if data is None:
            data = Path(payload["video_path"]).read_bytes()
        if not data:
            raise YouTubeError("empty video bytes", reason="VALIDATION")
        put = self._http.put(session_url, content=data,
                             headers={"Content-Type": "video/mp4",
                                      "Content-Length": str(len(data))})
        if put.status_code not in (200, 201):
            raise YouTubeError(
                f"upload put failed: {put.status_code} {put.text[:300]}",
                status=put.status_code, reason="UPLOAD_PUT_FAILED")
        video = put.json()
        vid = video["id"]
        return {
            "platform_post_id": vid,
            "remote_url": f"https://www.youtube.com/watch?v={vid}",
            "status": "PUBLISHED",
            "privacy_status": meta["status"]["privacyStatus"],
        }

    # ---------------------------------------------------------------- delete
    def delete_post(self, platform_post_id: str) -> dict:
        resp = self._http.post(
            f"{YOUTUBE_API_BASE}videos/delete?id={platform_post_id}",
            headers={"Authorization": "Bearer " + self._token})
        if resp.status_code not in (200, 204):
            raise YouTubeError(
                f"delete failed: {resp.status_code} {resp.text[:200]}",
                status=resp.status_code, reason="DELETE_FAILED")
        return {"deleted": True, "platform_post_id": platform_post_id}

    # --------------------------------------------------------------- metrics
    def get_metrics(self, platform_post_id: str) -> dict:
        resp = self._http.get(
            f"{YOUTUBE_API_BASE}videos",
            params={"part": "statistics,contentDetails", "id": platform_post_id},
            headers={"Authorization": "Bearer " + self._token})
        if resp.status_code != 200:
            raise YouTubeError(
                f"metrics failed: {resp.status_code} {resp.text[:200]}",
                status=resp.status_code, reason="METRICS_FAILED")
        items = resp.json().get("items") or []
        if not items:
            raise YouTubeError("video not found for metrics",
                               reason="NOT_FOUND")
        v = items[0]
        stats = v.get("statistics", {})
        return {
            "platform_post_id": platform_post_id,
            "views": int(stats.get("viewCount", 0) or 0),
            "likes": int(stats.get("likeCount", 0) or 0),
            "comments": int(stats.get("commentCount", 0) or 0),
            "duration": v.get("contentDetails", {}).get("duration", ""),
        }

    # ------------------------------------------------------- not supported
    def schedule_post(self, payload: dict, when_utc: str) -> dict:
        raise UnsupportedCapability("youtube adapter does not schedule posts yet")

    def read_comments(self, platform_post_id: str, *, limit: int = 50) -> list[dict]:
        raise UnsupportedCapability("youtube adapter does not read comments yet")

    def reply_comment(self, platform_post_id: str, comment_id: str, text: str) -> dict:
        raise UnsupportedCapability("youtube adapter does not reply to comments yet")

    def read_messages(self, *, limit: int = 50) -> list[dict]:
        raise UnsupportedCapability("youtube has no DM capability via this adapter")

    def reply_message(self, conversation_id: str, text: str) -> dict:
        raise UnsupportedCapability("youtube has no DM capability via this adapter")
