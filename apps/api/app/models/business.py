"""Core business models (spec §54).

Table families:
- identity/brand: brands, platform_accounts, platform_connections
- pipeline: opportunities, research_items, research_sources, opportunity_scores,
  content_items, strategies, scripts, script_versions
- production: assets, video_jobs, qc_results
- distribution: platform_variants, publish_jobs, published_posts
- engagement: interactions, responses, leads
- analytics: metric_snapshots, performance_scores
- learning: experiments, learning_patterns
- governance: cost_events, review_queue, audit_events, system_settings
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import JSONMixin, TimestampMixin, UUIDMixin, now_utc

# ---------------------------------------------------------------------------
# Identity / platform accounts
# ---------------------------------------------------------------------------


class Brand(UUIDMixin, TimestampMixin):
    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    niche: Mapped[str] = mapped_column(Text, default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class PlatformAccount(UUIDMixin, TimestampMixin, JSONMixin):
    __tablename__ = "platform_accounts"
    __table_args__ = (UniqueConstraint("brand_id", "platform", "handle", name="uq_platform_account"),)

    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    handle: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PlatformConnection(UUIDMixin, TimestampMixin, JSONMixin):
    """OAuth connection metadata. Tokens stay in the secret store; only references here."""

    __tablename__ = "platform_connections"

    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_accounts.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", nullable=False)
    external_app_id: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    scopes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    token_ref: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------------------------------------------------------------------------
# Pipeline: discovery -> research -> scoring -> selection
# ---------------------------------------------------------------------------


class Opportunity(UUIDMixin, TimestampMixin, JSONMixin):
    __tablename__ = "opportunities"
    __table_args__ = (
        Index("ix_opportunities_brand_created", "brand_id", "created_at"),
        UniqueConstraint("brand_id", "source", "source_id", name="uq_opportunity_source"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    engagement: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    trend: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)


class ResearchItem(UUIDMixin, TimestampMixin, JSONMixin):
    __tablename__ = "research_items"
    __table_args__ = (UniqueConstraint("opportunity_id", "depth", name="uq_research_depth"),)

    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    depth: Mapped[str] = mapped_column(String(32), default="STANDARD", nullable=False)
    facts: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    key_claims: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    content_gaps: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    competition: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchSource(UUIDMixin, TimestampMixin):
    __tablename__ = "research_sources"

    research_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_items.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    untrusted: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class OpportunityScore(UUIDMixin, TimestampMixin):
    __tablename__ = "opportunity_scores"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "version", name="uq_score_version"),
        CheckConstraint("total BETWEEN 0 AND 100", name="ck_score_total_range"),
    )

    opportunity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("opportunities.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    factors: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    penalties: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    total: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    scored_by: Mapped[str] = mapped_column(String(64), default="baseline_v1", nullable=False)


# ---------------------------------------------------------------------------
# Content production
# ---------------------------------------------------------------------------


class ContentItem(UUIDMixin, TimestampMixin, JSONMixin):
    __tablename__ = "content_items"
    __table_args__ = (
        Index("ix_content_state_created", "state", "created_at"),
        UniqueConstraint("brand_id", "dedup_hash", name="uq_content_dedup"),
    )

    brand_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("brands.id"), nullable=False)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("opportunities.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(32), default="DISCOVERED", nullable=False)
    state_history: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    dedup_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    human_review_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Strategy(UUIDMixin, TimestampMixin, JSONMixin):
    __tablename__ = "strategies"
    __table_args__ = (UniqueConstraint("content_item_id", name="uq_strategy_content"),)

    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    angle: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(Text, nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    format: Mapped[str] = mapped_column(String(64), default="short_video", nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    cta: Mapped[str] = mapped_column(Text, default="", nullable=False)
    objective: Mapped[str] = mapped_column(String(64), default="engagement", nullable=False)
    platforms: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)


class Script(UUIDMixin, TimestampMixin):
    __tablename__ = "scripts"
    __table_args__ = (UniqueConstraint("content_item_id", name="uq_script_current"),)

    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ScriptVersion(UUIDMixin, TimestampMixin):
    __tablename__ = "script_versions"
    __table_args__ = (UniqueConstraint("content_item_id", "version", name="uq_script_version"),)

    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    sections: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    full_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    fact_check: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_by: Mapped[str] = mapped_column(String(64), default="ai", nullable=False)


class VideoJob(UUIDMixin, TimestampMixin):
    __tablename__ = "video_jobs"
    __table_args__ = (Index("ix_video_jobs_status", "status"),)

    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    script_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("script_versions.id"), nullable=True)
    mpt_task_id: Mapped[str] = mapped_column(String(128), default="", nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="SUBMITTED", nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Asset(UUIDMixin, TimestampMixin):
    __tablename__ = "assets"
    __table_args__ = (Index("ix_assets_content_type", "content_item_id", "asset_type"),)

    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    checksum: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    duration: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Numeric(20, 0), default=0, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    video_job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("video_jobs.id"), nullable=True)


class QCResult(UUIDMixin, TimestampMixin):
    __tablename__ = "qc_results"
    __table_args__ = (UniqueConstraint("content_item_id", "attempt", name="uq_qc_attempt"),)

    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    checks: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    threshold_auto: Mapped[float] = mapped_column(Numeric(6, 2), default=85, nullable=False)
    threshold_review: Mapped[float] = mapped_column(Numeric(6, 2), default=70, nullable=False)
    decided_by: Mapped[str] = mapped_column(String(64), default="qc_engine", nullable=False)


class PlatformVariant(UUIDMixin, TimestampMixin, JSONMixin):
    __tablename__ = "platform_variants"
    __table_args__ = (UniqueConstraint("content_item_id", "platform", name="uq_variant_platform"),)

    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, default="", nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    hashtags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    cta: Mapped[str] = mapped_column(Text, default="", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class PublishJob(UUIDMixin, TimestampMixin):
    __tablename__ = "publish_jobs"
    __table_args__ = (
        UniqueConstraint("variant_id", "idempotency_key", name="uq_publish_idempotency"),
        Index("ix_publish_jobs_status", "status"),
    )

    variant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("platform_variants.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_post_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    remote_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    error_code: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    error_message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PublishedPost(UUIDMixin, TimestampMixin):
    __tablename__ = "published_posts"
    __table_args__ = (UniqueConstraint("platform", "platform_post_id", name="uq_published_post"),)

    publish_job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("publish_jobs.id"), nullable=False)
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_post_id: Mapped[str] = mapped_column(String(255), nullable=False)
    remote_url: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content_item_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_items.id"), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


# ---------------------------------------------------------------------------
# Engagement
# ---------------------------------------------------------------------------


class Interaction(UUIDMixin, TimestampMixin, JSONMixin):
    __tablename__ = "interactions"
    __table_args__ = (
        UniqueConstraint("platform", "platform_interaction_id", name="uq_interaction_platform"),
        Index("ix_interactions_created", "created_at"),
    )

    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_interaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_post_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    kind: Mapped[str] = mapped_column(String(24), nullable=False)  # COMMENT / MENTION / DM
    author_handle: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    body: Mapped[str] = mapped_column(Text, default="", nullable=False)
    classification: Mapped[str] = mapped_column(String(32), default="UNKNOWN", nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Numeric(5, 2), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


class Response(UUIDMixin, TimestampMixin):
    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("interaction_id", name="uq_response_interaction"),)

    interaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("interactions.id"), nullable=False)
    # AUTO_REPLY / DRAFT / HUMAN_REQUIRED / IGNORE
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    draft_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    sent_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT", nullable=False)
    platform_reply_id: Mapped[str] = mapped_column(String(255), default="", nullable=False)
    decided_by: Mapped[str] = mapped_column(String(64), default="policy_engine", nullable=False)


class Lead(UUIDMixin, TimestampMixin):
    __tablename__ = "leads"

    interaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("interactions.id"), nullable=True)
    handle: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    platform: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    stage: Mapped[str] = mapped_column(String(32), default="NEW", nullable=False)
    intent: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", nullable=False)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class MetricSnapshot(UUIDMixin, TimestampMixin):
    __tablename__ = "metric_snapshots"
    __table_args__ = (
        UniqueConstraint("published_post_id", "captured_at", "metric_key", name="uq_metric_snapshot"),
        Index("ix_metric_snapshots_key_time", "metric_key", "captured_at"),
    )

    published_post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("published_posts.id"), nullable=False)
    metric_key: Mapped[str] = mapped_column(String(48), nullable=False)
    # NULL = unsupported (spec §38)
    value: Mapped[float | None] = mapped_column(Numeric(18, 4), nullable=True)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="platform_api", nullable=False)


class PerformanceScore(UUIDMixin, TimestampMixin):
    __tablename__ = "performance_scores"
    __table_args__ = (UniqueConstraint("published_post_id", name="uq_performance_post"),)

    published_post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("published_posts.id"), nullable=False)
    score: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    components: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    computed_by: Mapped[str] = mapped_column(String(64), default="performance_engine", nullable=False)


# ---------------------------------------------------------------------------
# Learning
# ---------------------------------------------------------------------------


class Experiment(UUIDMixin, TimestampMixin):
    __tablename__ = "experiments"

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, default="", nullable=False)
    # topic/angle/hook/duration/format/cta/platform
    dimension: Mapped[str] = mapped_column(String(48), nullable=False)
    variant_a: Mapped[str] = mapped_column(JSONB, default=dict, nullable=False)
    variant_b: Mapped[str] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="RUNNING", nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class LearningPattern(UUIDMixin, TimestampMixin):
    __tablename__ = "learning_patterns"
    __table_args__ = (UniqueConstraint("dimension", "value", name="uq_learning_dimension_value"),)

    dimension: Mapped[str] = mapped_column(String(48), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mean_performance: Mapped[float] = mapped_column(Numeric(10, 4), default=0, nullable=False)
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), default=0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc, nullable=False)


# ---------------------------------------------------------------------------
# Governance: cost, review, audit, settings
# ---------------------------------------------------------------------------


class CostEvent(UUIDMixin, TimestampMixin):
    __tablename__ = "cost_events"
    __table_args__ = (Index("ix_cost_events_day", "created_at"),)

    # llm / video / storage / platform / infra
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    content_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_items.id"), nullable=True)
    workflow_run_id: Mapped[str] = mapped_column(String(128), default="", nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class ReviewQueue(UUIDMixin, TimestampMixin):
    __tablename__ = "review_queue"
    __table_args__ = (Index("ix_review_queue_status", "status"),)

    content_item_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_items.id"), nullable=True)
    interaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("interactions.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="MEDIUM", nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="PENDING", nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(24), nullable=True)
    resolved_by: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(UUIDMixin, TimestampMixin):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_time", "created_at"),)

    actor: Mapped[str] = mapped_column(String(64), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(96), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    entity_id: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), default="OK", nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class SystemSetting(UUIDMixin, TimestampMixin):
    __tablename__ = "system_settings"
    __table_args__ = (UniqueConstraint("key", name="uq_system_setting_key"),)

    key: Mapped[str] = mapped_column(String(96), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)


__all__ = [
    "Asset",
    "AuditEvent",
    "Brand",
    "ContentItem",
    "CostEvent",
    "Experiment",
    "Interaction",
    "Lead",
    "LearningPattern",
    "MetricSnapshot",
    "Opportunity",
    "OpportunityScore",
    "PerformanceScore",
    "PlatformAccount",
    "PlatformConnection",
    "PlatformVariant",
    "PublishedPost",
    "PublishJob",
    "QCResult",
    "ResearchItem",
    "ResearchSource",
    "Response",
    "ReviewQueue",
    "Script",
    "ScriptVersion",
    "Strategy",
    "SystemSetting",
    "VideoJob",
]
