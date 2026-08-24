"""PlatformAdapter interface + capability discovery (spec §34).

Unsupported operations are explicit UnsupportedCapability errors — never faked.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class UnsupportedCapability(Exception):
    """The platform genuinely does not support this operation."""


@dataclass(frozen=True)
class Capabilities:
    publish_video: bool = False
    schedule_post: bool = False
    read_comments: bool = False
    reply_comment: bool = False
    read_messages: bool = False
    reply_message: bool = False
    get_metrics: bool = False
    delete_post: bool = False

    def to_list(self) -> list[str]:
        return [k for k, v in self.__dict__.items() if v]


class PlatformAdapter(Protocol):
    platform: str
    capabilities: Capabilities

    def publish_video(self, payload: dict) -> dict: ...
    def schedule_post(self, payload: dict, when_utc: str) -> dict: ...
    def read_comments(self, platform_post_id: str, *, limit: int = 50) -> list[dict]: ...
    def reply_comment(self, platform_post_id: str, comment_id: str, text: str) -> dict: ...
    def read_messages(self, *, limit: int = 50) -> list[dict]: ...
    def reply_message(self, conversation_id: str, text: str) -> dict: ...
    def get_metrics(self, platform_post_id: str) -> dict: ...
    def delete_post(self, platform_post_id: str) -> dict: ...


def requireCapability(adapter, name: str):
    cap = getattr(adapter.capabilities, name, False)
    if not cap:
        raise UnsupportedCapability(
            f"platform {adapter.platform} does not support {name}"
        )


class DryRunAdapter:
    """Dry-run publishing adapter (spec §57): generates the exact platform payload,
    records what WOULD be published, performs zero external side effects."""

    platform = "dryrun"
    capabilities = Capabilities(
        publish_video=True,
        schedule_post=True,
        read_comments=False,
        reply_comment=False,
        read_messages=False,
        reply_message=False,
        get_metrics=False,
        delete_post=False,
    )

    def __init__(self):
        self.published: list[dict] = []

    def publish_video(self, payload: dict) -> dict:
        record = {"mode": "DRY_RUN", "platform": "dryrun", "payload": payload,
                  "would_publish": True}
        self.published.append(record)
        return {"status": "DRY_RUN", "platform_post_id": "", "remote_url": "",
                "detail": record}

    def schedule_post(self, payload: dict, when_utc: str) -> dict:
        record = {"mode": "DRY_RUN", "platform": "dryrun", "payload": payload,
                  "scheduled_for": when_utc}
        self.published.append(record)
        return {"status": "DRY_RUN_SCHEDULED", "platform_post_id": "", "remote_url": "",
                "detail": record}

    def read_comments(self, platform_post_id, *, limit=50):
        raise UnsupportedCapability("dryrun adapter does not read comments")

    def reply_comment(self, platform_post_id, comment_id, text):
        raise UnsupportedCapability("dryrun adapter does not reply")

    def read_messages(self, *, limit=50):
        raise UnsupportedCapability("dryrun adapter does not read messages")

    def reply_message(self, conversation_id, text):
        raise UnsupportedCapability("dryrun adapter does not reply")

    def get_metrics(self, platform_post_id):
        raise UnsupportedCapability("dryrun adapter does not fetch metrics")

    def delete_post(self, platform_post_id):
        raise UnsupportedCapability("dryrun adapter does not delete")
