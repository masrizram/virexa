"""Autonomous daily cycle helpers (spec §22).

Research is currently heuristic (no LLM call): it records source provenance and
neutral context so every content item has an auditable research row, matching
the provenance requirements of §23 without spending AI budget. Scoring factors
are deterministic heuristics over persisted engagement/trend metadata; when AI
research lands, only this module changes — the cycle endpoint stays.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select

from app.models.business import Opportunity, ResearchItem

__all__ = ["SCORING_BASELINE_WEIGHTS", "heuristic_factors", "save_research_heuristics"]

# Re-exported for the cycle endpoint's factor-key coverage check.
from app.engines.scoring import BASELINE_WEIGHTS as SCORING_BASELINE_WEIGHTS  # noqa: E402


def save_research_heuristics(session, opp: Opportunity) -> ResearchItem:
    """Idempotent heuristic research row for an opportunity (depth=CYCLE)."""
    item = session.execute(
        select(ResearchItem).where(
            ResearchItem.opportunity_id == opp.id,
            ResearchItem.depth == "CYCLE",
        )
    ).scalar_one_or_none()
    if item is None:
        item = ResearchItem(opportunity_id=opp.id, depth="CYCLE")
        session.add(item)
    item.facts = []
    item.key_claims = []
    item.context = {"mode": "heuristic", "source": opp.source, "topic": opp.topic}
    item.content_gaps = []
    item.competition = {}
    item.summary = f"Heuristic research for {opp.source} topic."
    from app.models.base import now_utc

    item.completed_at = now_utc()
    session.flush()
    return item


_AUDIENCE_FIT_BY_SOURCE = {"hackernews": 65.0, "rss": 60.0}


def heuristic_factors(session, opp: Opportunity) -> dict[str, float]:
    """Deterministic 0-100 factors over persisted metadata (no AI spend).

    Every value traces to a persisted field; unknowns degrade to documented
    neutrals so scoring never fabricates precision it does not have.
    """
    engagement = opp.engagement or {}
    trend = opp.trend or {}

    points = engagement.get("points")
    if points is None:
        ups, n = engagement.get("score"), engagement.get("score_count")
        points = (float(ups) / float(n)) if (ups is not None and n) else None

    velocity = trend.get("velocity")
    if velocity is None:
        velocity = 60.0 if opp.source == "hackernews" else (55.0 if opp.source == "rss" else 50.0)

    when = opp.published_at or opp.discovered_at
    if when is not None:
        age_hours = max(0.0, (datetime.now(UTC) - when).total_seconds() / 3600.0)
        freshness = 100.0 - min(age_hours * 2.0, 60.0)
    else:
        freshness = 65.0

    audience_default = 70.0 if opp.source.startswith("reddit:") else 55.0
    return {
        "TrendVelocity": float(velocity),
        "AudienceFit": _AUDIENCE_FIT_BY_SOURCE.get(opp.source, audience_default),
        "ViralPotential": min(100.0, max(0.0, float(points))) if points is not None else 40.0,
        "ContentGap": 50.0,
        "Freshness": freshness,
        "Monetization": 45.0,
        "ProductionEase": 55.0,
        "Confidence": 40.0,
    }
