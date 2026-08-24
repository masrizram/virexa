"""MoneyPrinterTurbo typed client (spec §31).

Explicit timeouts, bounded polling, checksum validation. HTTP 200 is not proof:
validate task status AND output parameters AND downloadable result before trusting.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass

import httpx


class MPTError(Exception):
    def __init__(self, message: str, *, code: str = "UNKNOWN"):
        self.code = code
        super().__init__(message)


@dataclass
class MPTTaskResult:
    task_id: str
    status: str  # PENDING / PROGRESS / COMPLETED / FAILED
    progress: float
    videos: list


class MPTClient:
    """Client for MoneyPrinterTurbo /v1 API."""

    def __init__(self, base_url: str, *, secret: str = "", timeout: float = 30.0,
                 poll_interval: float = 3.0, max_poll_seconds: float = 900.0, transport=None):
        self.base_url = base_url.rstrip("/")
        self._secret = secret
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._max_poll_seconds = max_poll_seconds
        self._client = httpx.Client(base_url=self.base_url, timeout=timeout, transport=transport)

    def _headers(self):
        if self._secret:
            return {"Authorization": "Bearer " + self._secret}
        return {}

    def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            resp = self._client.get(path, params=params, headers=self._headers())
        except httpx.HTTPError as exc:
            raise MPTError("MPT transport error: " + str(exc), code="TRANSIENT") from exc
        if resp.status_code >= 500:
            raise MPTError("MPT server error " + str(resp.status_code), code="TRANSIENT")
        if resp.status_code == 404:
            raise MPTError("MPT endpoint not found", code="VALIDATION")
        if resp.status_code != 200:
            raise MPTError("MPT unexpected status " + str(resp.status_code), code="UNKNOWN")
        data = resp.json()
        if data.get("status") != 200:
            raise MPTError("MPT business error: " + str(data.get("message", "unknown")), code="DEPENDENCY")
        return data.get("data", {})

    def health(self) -> dict:
        try:
            resp = self._client.get("/health", headers=self._headers())
        except httpx.HTTPError as exc:
            raise MPTError("MPT health transport error: " + str(exc), code="TRANSIENT") from exc
        if resp.status_code != 200:
            raise MPTError("MPT health status " + str(resp.status_code), code="UNKNOWN")
        return {"ok": True}

    def submit_job(self, params: dict) -> dict:
        """POST /v1/videos with MPT task params; returns created task data."""
        try:
            resp = self._client.post("/v1/videos", json=params, headers=self._headers())
        except httpx.HTTPError as exc:
            raise MPTError("MPT submit transport error: " + str(exc), code="TRANSIENT") from exc
        if resp.status_code != 200:
            raise MPTError("MPT submit status " + str(resp.status_code), code="UNKNOWN")
        data = resp.json()
        if data.get("status") != 200:
            raise MPTError("MPT submit business error: " + str(data.get("message")), code="DEPENDENCY")
        return data.get("data", {})

    def get_status(self, task_id: str) -> MPTTaskResult:
        data = self._get("/v1/stream/" + task_id, params={"task_id": task_id})
        state = data.get("state", "")
        videos = list(data.get("videos", []) or []) + list(data.get("combinedVideos", []) or [])
        if not state:
            state = "COMPLETED" if videos else "PENDING"
        return MPTTaskResult(
            task_id=task_id,
            status=state,
            progress=float(data.get("progress", 0) or 0),
            videos=videos,
        )

    def wait_for_job(self, task_id: str, on_poll=None) -> MPTTaskResult:
        """Poll until COMPLETED/FAILED or timeout."""
        deadline = time.monotonic() + self._max_poll_seconds
        while True:
            result = self.get_status(task_id)
            if on_poll:
                on_poll(result)
            if result.status in ("COMPLETED", "FAILED"):
                return result
            if time.monotonic() >= deadline:
                raise MPTError("MPT task " + task_id + " timed out after "
                               + str(self._max_poll_seconds) + "s", code="TIMEOUT")
            time.sleep(self._poll_interval)

    def validate_output(self, result: MPTTaskResult) -> dict:
        """HTTP 200 is not proof: task must be COMPLETED with output URLs."""
        if result.status != "COMPLETED":
            raise MPTError("MPT task not completed: " + result.status, code="VALIDATION")
        if not result.videos:
            raise MPTError("MPT completed but no video output", code="VALIDATION")
        return {"ok": True, "videos": result.videos}

    def download_result(self, result: MPTTaskResult, dest_path: str) -> str:
        validated = self.validate_output(result)
        url = ""
        for video in validated["videos"]:
            if video.get("url"):
                url = video["url"]
                break
        if not url:
            raise MPTError("MPT video URL missing", code="VALIDATION")
        if not url.startswith("http"):
            raise MPTError("MPT returned non-http video path; fetch via MPT file endpoint",
                           code="VALIDATION")
        resp = self._client.get(url, headers=self._headers())
        if resp.status_code != 200:
            raise MPTError("MPT download status " + str(resp.status_code), code="TRANSIENT")
        with open(dest_path, "wb") as f:
            f.write(resp.content)
        return dest_path

    @staticmethod
    def checksum(path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    def close(self):
        self._client.close()
