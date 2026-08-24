"""AI failover chain (spec §28): PRIMARY -> SECONDARY -> DEFER/REVIEW.

Bounded attempts, per-attempt usage recorded, cost summed.
"""
from __future__ import annotations

from app.ai.provider import AIProvider, AIProviderError, AITask


class AIAllProvidersFailedError(AIProviderError):
    """Every provider in the chain failed; caller must DEFER/REVIEW."""


class AIChain:
    def __init__(self, providers: list[AIProvider]):
        if not providers:
            raise ValueError("AIChain requires at least one provider")
        self.providers = providers

    def complete(self, task: AITask, system: str, prompt: str, *, json_mode: bool = False,
                 timeout: float = 60.0):
        attempts = []
        last_error: AIProviderError | None = None
        for provider in self.providers:
            try:
                result = provider.complete(task, system, prompt, json_mode=json_mode, timeout=timeout)
                result.attempts = attempts + result.attempts
                return result
            except AIProviderError as exc:
                attempts.append(exc)
                last_error = exc
                # AUTH errors are not retried against the same provider, move on.
        raise AIAllProvidersFailedError(
            f"All {len(self.providers)} providers failed for task {task.value}; "
            f"last: {last_error}",
            provider="chain",
            kind=last_error.kind if last_error else "UNKNOWN",
        )
