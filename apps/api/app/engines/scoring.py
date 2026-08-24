"""Opportunity scoring engine (spec §25).

Baseline weights sum to 100. Penalties subtract. Total clamped to [0, 100].
Every factor and penalty is persisted in opportunity_scores.factors/penalties.
"""

BASELINE_WEIGHTS = {
    "TrendVelocity": 20.0,
    "AudienceFit": 20.0,
    "ViralPotential": 15.0,
    "ContentGap": 15.0,
    "Freshness": 10.0,
    "Monetization": 10.0,
    "ProductionEase": 5.0,
    "Confidence": 5.0,
}

PENALTY_KEYS = ("RiskPenalty", "SaturationPenalty", "DuplicatePenalty", "EvidencePenalty")


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def compute_score(factors, penalties=None, weights=None):
    """Compute total score from raw factor values (0-100 each).

    Returns (total, weighted_factors, applied_penalties).
    Raises ValueError if factor keys do not cover the configured weights.
    """
    w = weights or BASELINE_WEIGHTS
    missing = [k for k in w if k not in factors]
    if missing:
        raise ValueError("Missing factor values: " + ", ".join(sorted(missing)))

    weighted = {}
    total = 0.0
    for key in w:
        weight = w[key]
        raw = clamp(float(factors[key]))
        contribution = raw * weight / 100.0
        weighted[key] = round(contribution, 4)
        total = total + contribution

    applied = {}
    if penalties:
        for pkey in PENALTY_KEYS:
            if pkey in penalties:
                val = max(0.0, float(penalties[pkey]))
                applied[pkey] = round(val, 4)
                total = total - val

    return round(clamp(total), 2), weighted, applied


def classify_verdict(total, auto=85.0, review=70.0):
    if total >= auto:
        return "AUTO_SELECT"
    if total >= review:
        return "CONSIDER"
    return "SKIP"
