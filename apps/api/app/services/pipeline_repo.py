"""Pipeline persistence helpers: brands, opportunities, research, content items."""
from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.engines.dedup import dedup_hash, is_duplicate
from app.models.business import Brand, ContentItem, Opportunity, ResearchItem, ResearchSource


def get_default_brand(session: Session, name: str = "default") -> Brand:
    brand = session.execute(select(Brand).where(Brand.name == name)).scalar_one_or_none()
    if brand is None:
        brand = Brand(name=name, niche="")
        session.add(brand)
        session.flush()
    return brand


def upsert_opportunity(session: Session, brand_id, *, source: str, source_id: str,
                       topic: str, url: str = "", published_at=None, engagement: dict | None = None,
                       trend: dict | None = None, raw_metadata: dict | None = None) -> tuple[Opportunity, bool]:
    """Insert opportunity unless (source, source_id) exists. Returns (row, created)."""
    existing = session.execute(
        select(Opportunity).where(
            Opportunity.brand_id == brand_id,
            Opportunity.source == source,
            Opportunity.source_id == source_id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing, False
    row = Opportunity(
        brand_id=brand_id,
        source=source,
        source_id=source_id,
        topic=topic,
        url=url or "",
        published_at=published_at,
        engagement=engagement or {},
        trend=trend or {},
        raw_metadata=raw_metadata or {},
        dedup_hash=dedup_hash(topic, source, source_id),
    )
    session.add(row)
    session.flush()
    return row, True


def recent_topics(session: Session, brand_id, *, days: int = 30, limit: int = 200) -> list[str]:
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=days)
    rows = session.execute(
        select(Opportunity.topic)
        .where(Opportunity.brand_id == brand_id, Opportunity.discovered_at >= since)
        .order_by(Opportunity.discovered_at.desc())
        .limit(limit)
    ).scalars().all()
    return list(rows)


def create_content_item(session: Session, brand_id, *, title: str, opportunity_id=None) -> ContentItem:
    from app.engines.dedup import topic_hash

    item = ContentItem(
        brand_id=brand_id,
        opportunity_id=opportunity_id,
        title=title,
        state="DISCOVERED",
        dedup_hash=topic_hash(title),
        state_history=[],
    )
    session.add(item)
    session.flush()
    return item


def content_history_titles(session: Session, brand_id, *, days: int = 60, limit: int = 300) -> list[str]:
    from datetime import UTC, datetime, timedelta

    since = datetime.now(UTC) - timedelta(days=days)
    rows = session.execute(
        select(ContentItem.title)
        .where(ContentItem.brand_id == brand_id, ContentItem.created_at >= since)
        .order_by(ContentItem.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return list(rows)


def check_duplicate_topic(session: Session, brand_id, topic: str) -> tuple[bool, float, str | None]:
    return is_duplicate(topic, recent_topics(session, brand_id) + content_history_titles(session, brand_id))


def save_research(session: Session, opportunity_id, *, facts: list, key_claims: list,
                  context: dict, content_gaps: list, competition: dict, summary: str,
                  sources: list[dict], depth: str = "STANDARD") -> ResearchItem:
    # Idempotent upsert: (opportunity_id, depth) is unique — re-research replaces.
    item = session.execute(
        select(ResearchItem).where(
            ResearchItem.opportunity_id == opportunity_id,
            ResearchItem.depth == depth,
        )
    ).scalar_one_or_none()
    if item is None:
        item = ResearchItem(opportunity_id=opportunity_id, depth=depth)
        session.add(item)
    item.facts = facts
    item.key_claims = key_claims
    item.context = context
    item.content_gaps = content_gaps
    item.competition = competition
    item.summary = summary
    from app.models.base import now_utc

    item.completed_at = now_utc()
    session.flush()
    # Replace sources of this research item on re-run (idempotency).
    session.execute(
        delete(ResearchSource).where(ResearchSource.research_item_id == item.id)
    )
    for src in sources:
        session.add(ResearchSource(
            research_item_id=item.id,
            url=src.get("url", ""),
            title=src.get("title", ""),
            published_at=src.get("published_at"),
            excerpt=(src.get("excerpt") or "")[:2000],
            untrusted=True,
        ))
    return item
