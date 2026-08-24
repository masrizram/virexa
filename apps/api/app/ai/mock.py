"""Deterministic mock provider for tests/dry-run ONLY (opt-in via AI_ALLOW_MOCK)."""
from __future__ import annotations

from app.ai.provider import AIResult, AITask, AIUsage


class MockProvider:
    name = "mock"

    def __init__(self, responder=None):
        self.calls: list[dict] = []
        self._responder = responder or (lambda task, system, prompt: f"MOCK:{task.value}:{prompt[:40]}")

    def complete(self, task: AITask, system: str, prompt: str, *, json_mode: bool = False,
                 timeout: float = 60.0) -> AIResult:
        self.calls.append({"task": task, "system": system, "prompt": prompt, "json_mode": json_mode})
        usage = AIUsage(provider="mock", model="mock-1", input_tokens=len(prompt) // 4,
                        output_tokens=64, success=True)
        return AIResult(text=self._responder(task, system, prompt), usage=usage, attempts=[usage])
