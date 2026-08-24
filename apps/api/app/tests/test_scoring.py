"""Scoring engine tests (spec §25)."""
import pytest

from app.engines.scoring import BASELINE_WEIGHTS, compute_score


def test_weights_sum_to_100():
    assert sum(BASELINE_WEIGHTS.values()) == 100.0


def test_perfect_score():
    factors = {k: 100.0 for k in BASELINE_WEIGHTS}
    total, weighted, applied = compute_score(factors)
    assert total == 100.0
    assert applied == {}
    assert weighted["TrendVelocity"] == 20.0


def test_zero_score():
    factors = {k: 0.0 for k in BASELINE_WEIGHTS}
    total, _, _ = compute_score(factors)
    assert total == 0.0


def test_missing_factor_raises():
    factors = {k: 50.0 for k in BASELINE_WEIGHTS}
    del factors["Freshness"]
    with pytest.raises(ValueError, match="Freshness"):
        compute_score(factors)


def test_penalty_subtracts_and_clamps():
    factors = {k: 10.0 for k in BASELINE_WEIGHTS}
    total, _, applied = compute_score(factors, {"RiskPenalty": 50.0})
    assert total == 0.0  # 10 - 50 clamped to 0
    assert applied == {"RiskPenalty": 50.0}


def test_factor_clamping():
    factors = {k: 500.0 for k in BASELINE_WEIGHTS}  # above 100 clamps to 100
    total, _, _ = compute_score(factors)
    assert total == 100.0
