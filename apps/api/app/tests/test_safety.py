"""Safety state + budget guard tests (spec §42, §53)."""
import pytest

from app.core.safety import (
    BudgetExceededError,
    SafetyBlockedError,
    SafetyState,
    side_effect_allowed,
)


def test_default_running_allows_when_not_dry():
    ok, reason = side_effect_allowed("RUNNING", dry_run=False)
    assert ok and reason == "OK"


def test_dry_run_blocks():
    ok, reason = side_effect_allowed("RUNNING", dry_run=True)
    assert not ok and reason == "DRY_RUN"


def test_paused_blocks():
    ok, reason = side_effect_allowed("PAUSED", dry_run=False)
    assert not ok and reason == "PAUSED"


def test_emergency_stop_blocks():
    ok, reason = side_effect_allowed("EMERGENCY_STOP", dry_run=False)
    assert not ok and reason == "EMERGENCY_STOP"


def test_invalid_state_raises():
    with pytest.raises(ValueError):
        side_effect_allowed("SPEEDING", dry_run=False)
