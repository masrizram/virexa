"""AI provider abstraction (spec §27-28).

Task classes map to provider chains. Business code never binds to one model.
Failover: PRIMARY -> SECONDARY -> DEFER/REVIEW. No infinite retries.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import httpx


class AITask(str, Enum):
    DEEP_REASONING = "DEEP_REASONING"
    RESEARCH_SYNTHESIS = "RESEARCH_SYNTHESIS"
    FAST_GENERATION = "FAST_GENERATION"
    CLASSIFICATION = "CLASSIFICATION"
    COPYWRITING = "COPYWRITING"


@dataclass
class AIUsage:
    provider: str = ""
    model: str = ""
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    success: bool = False
    error: str = ""


@dataclass
class AIResult:
    text: str = ""
    usage: AIUsage = field(default_factory=AIUsage)
    attempts: list[AIUsage] = field(default_factory=list)


class AIProviderError(Exception):
    def __init__(self, message: str, *, provider: str = "", kind: str = "UNKNOWN"):
        self.provider = provider
        self.kind = kind  # TRANSIENT / RATE_LIMIT / AUTH / VALIDATION / UNKNOWN
        super().__init__(message)


class AIProvider(Protocol):
    name: str

    def complete(self, task: AITask, system: str, prompt: str, *, json_mode: bool = False,
                 timeout: float = 60.0) -> AIResult: ...


# Pricing USD per 1M tokens (input, output). Updated from provider pricing pages.
PRICING_PER_MTOK: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "glm-4-flash": (0.0, 0.0),
    "moonshot-v1-8k": (1.20, 1.20),
}


@dataclass
class OpenAICompatProvider:
    """OpenAI-compatible chat completions endpoint (OpenAI, GLM, Kimi, local, ...)."""

    name: str
    base_url: str
    api_key: str
    model: str

    def complete(self, task: AITask, system: str, prompt: str, *, json_mode: bool = False,
                 timeout: float = 60.0) -> AIResult:
        url = self.base_url.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.4,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        start = time.monotonic()
        usage = AIUsage(provider=self.name, model=self.model)
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=timeout)
        except httpx.HTTPError as exc:
            usage.error = str(exc)
            usage.latency_ms = (time.monotonic() - start) * 1000
            raise AIProviderError(f"{self.name}: transport error: {exc}", provider=self.name,
                                  kind="TRANSIENT") from exc

        usage.latency_ms = (time.monotonic() - start) * 1000
        if resp.status_code in (429,):
            raise AIProviderError(f"{self.name}: rate limited", provider=self.name, kind="RATE_LIMIT")
        if resp.status_code in (401, 403):
            raise AIProviderError(f"{self.name}: auth failed", provider=self.name, kind="AUTH")
        if resp.status_code >= 500:
            raise AIProviderError(f"{self.name}: server error {resp.status_code}", provider=self.name,
                                  kind="TRANSIENT")
        if resp.status_code != 200:
            raise AIProviderError(f"{self.name}: unexpected status {resp.status_code}",
                                  provider=self.name, kind="UNKNOWN")

        data = resp.json()
        try:
            usage.input_tokens = int(data.get("usage", {}).get("prompt_tokens", 0))
            usage.output_tokens = int(data.get("usage", {}).get("completion_tokens", 0))
        except (TypeError, ValueError):
            pass
        pin, pout = PRICING_PER_MTOK.get(self.model, (0.0, 0.0))
        usage.cost = round(usage.input_tokens / 1e6 * pin + usage.output_tokens / 1e6 * pout, 8)

        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as exc:
            raise AIProviderError(f"{self.name}: malformed response", provider=self.name,
                                  kind="VALIDATION") from exc
        usage.success = True
        return AIResult(text=text, usage=usage, attempts=[usage])
