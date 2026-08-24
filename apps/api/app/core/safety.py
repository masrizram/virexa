"""Safety state (spec §53) and budget guard helpers (spec §42).

The global safety state lives in system_settings and gates every external
side effect: publishing, comment replies, DM replies.
"""
from __future__ import annotations

from enum import StrEnum


class SafetyState(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    EMERGENCY_STOP = "EMERGENCY_STOP"


SAFETY_SETTINGS_KEY = "safety_state"

# Budget keys (spec §42) stored in system_settings['budgets'].
BUDGET_DEFAULTS: dict[str, float] = {
    "daily_llm_budget": 10.0,
    "daily_video_budget": 5.0,
    "daily_total_budget": 20.0,
    "daily_content_limit": 3,
    "platform_daily_limit": 5,
}


class SafetyBlockedError(Exception):
    """Raised when an external side effect is blocked by safety state."""


class BudgetExceededError(Exception):
    """Raised when an operation would exceed a configured daily budget."""

    def __init__(self, budget: str, spent: float, limit: float):
        self.budget = budget
        self.spent = spent
        self.limit = limit
        super().__init__(f"Budget '{budget}' exceeded: spent={spent:.4f} limit={limit:.4f}")


def side_effect_allowed(safety: str, dry_run: bool) -> tuple[bool, str]:
    """Decide whether an external side effect may proceed.

    Returns (allowed, reason). Reasons are stable strings for audit logs.
    """
    state = SafetyState(safety)
    if state == SafetyState.EMERGENCY_STOP:
        return False, "EMERGENCY_STOP"
    if state == SafetyState.PAUSED:
        return False, "PAUSED"
    if dry_run:
        return False, "DRY_RUN"
    return True, "OK"
