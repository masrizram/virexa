"""Pipeline orchestration API consumed by Windmill workers.

Design (spec §19): business logic lives in FastAPI; Windmill orchestrates only.
Each endpoint is idempotent-safe for its stage and writes audit events.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.config import get_settings
from app.core.safety import side_effect_allowed
from app.engines import adaptation as adaptation_engine
from app.engines import qc as qc_engine
from app.engines.discovery import (
    ConnectorResult,
    discover_hackernews,
    discover_reddit,
    discover_rss,
)
from app.models.business import (
    Asset,
    ContentItem,
    OpportunityScore,
    PlatformVariant,
    PublishJob,
    QCResult,
    Script,
    ScriptVersion,
    Strategy,
    VideoJob,
)
from app.mpt.client import MPTClient
from app.services import pipeline_repo
from app.services.cost_service import spend_and_record
from app.services.state_service import audit, get_safety_state, transition_content
from app.services.storage import StorageService

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

DISCOVERY_SOURCES_DEFAULT = ["hackernews", "reddit:technology", "rss"]
REDDIT_SUBS_DEFAULT = ["technology", "programming", "artificial", "gadgets"]
RSS_FEEDS_DEFAULT = [
    "https://hnrss.org/frontpage",
    "https://feeds.arstechnica.com/arstechnica/index",
]


class DiscoverRequest(BaseModel):
    brand: str = "default"
    sources: list[str] | None = None
    limit_per_source: int = 20


class ResearchRequest(BaseModel):
    opportunity_id: uuid.UUID
    facts: list = Field(default_factory=list)
    key_claims: list = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    content_gaps: list = Field(default_factory=list)
    competition: dict = Field(default_factory=dict)
    summary: str = ""
    sources: list[dict] = Field(default_factory=list)
    depth: str = "STANDARD"


class ScoreOpportunityRequest(BaseModel):
    opportunity_id: uuid.UUID
    factors: dict[str, float]
    penalties: dict[str, float] | None = None


class SelectRequest(BaseModel):
    opportunity_id: uuid.UUID
    title: str
    content_item_id: uuid.UUID | None = None


class StrategyRequest(BaseModel):
    content_item_id: uuid.UUID
    topic: str
    angle: str
    audience: str
    hook: str
    format: str = "short_video"
    duration_seconds: int = 60
    cta: str = ""
    objective: str = "engagement"
    platforms: list[str] = Field(default_factory=lambda: ["youtube", "tiktok"])


class ScriptRequest(BaseModel):
    content_item_id: uuid.UUID
    sections: dict  # HOOK/CONTEXT/CORE/PAYOFF/CTA
    fact_check: dict = Field(default_factory=dict)
    created_by: str = "ai"
    cost_usd: float = 0.0


class ProduceVideoRequest(BaseModel):
    content_item_id: uuid.UUID
    script_version_id: uuid.UUID
    mpt_task_id: str
    params: dict = Field(default_factory=dict)
    cost_usd: float = 0.0


class VideoCompleteRequest(BaseModel):
    video_job_id: uuid.UUID
    status: str  # COMPLETED / FAILED
    assets: list[dict] = Field(default_factory=list)
    error_code: str = ""
    error_message: str = ""


class ProduceSyncRequest(BaseModel):
    """Poll MPT for a video job, download, upload to S3, record Asset (§19/§31/§18)."""
    video_job_id: uuid.UUID
    poll_timeout_seconds: float = 60.0


def _get_mpt_client() -> MPTClient:
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.mpt_base_url:
        raise HTTPException(503, "MPT not configured")
    return MPTClient(settings.mpt_base_url)


def _get_storage() -> StorageService:
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.s3_bucket:
        raise HTTPException(503, "S3 storage not configured")
    return StorageService(
        endpoint=settings.s3_endpoint, region=settings.s3_region,
        bucket=settings.s3_bucket, access_key=settings.s3_access_key_id,
        secret_key=settings.s3_secret_access_key,
    )


class QCRequest(BaseModel):
    content_item_id: uuid.UUID
    video_exists: bool = True
    file_readable: bool = True
    duration: float | None = None
    expected_duration: float | None = None
    resolution: list[int] | None = None
    has_audio: bool | None = None
    has_subtitle: bool = False
    subtitle_aligns: bool | None = None
    branding_ok: bool | None = None
    script_alignment_score: float | None = None
    duplicate_risk: float = 0.0
    fact_risk: float = 0.0
    platform_constraint_violations: list[str] = Field(default_factory=list)
    threshold_auto: float = 85.0
    threshold_review: float = 70.0


class AdaptRequest(BaseModel):
    content_item_id: uuid.UUID
    platforms: list[str]
    title: str = ""
    hook: str = ""
    description: str = ""
    cta: str = ""
    hashtags: list[str] = Field(default_factory=list)


class PublishRequest(BaseModel):
    variant_id: uuid.UUID
    idempotency_key: str
    payload: dict = Field(default_factory=dict)
    platform_post_id: str = ""  # set when adapter published (or DRY_RUN marker)
    remote_url: str = ""
    status: str = "PUBLISHED"  # PUBLISHED / DRY_RUN / FAILED
    error_code: str = ""
    error_message: str = ""


@router.post("/discover")
def discover(req: DiscoverRequest, session: Session = Depends(db_session)):
    """Run discovery connectors and persist normalized opportunities."""
    brand = pipeline_repo.get_default_brand(session, req.brand)
    results: list[ConnectorResult] = []
    sources = req.sources or DISCOVERY_SOURCES_DEFAULT

    if "hackernews" in sources:
        results.append(discover_hackernews(limit=req.limit_per_source))
    for s in sources:
        if s.startswith("reddit:"):
            results.append(discover_reddit([s.split(":", 1)[1]], limit_per_sub=req.limit_per_source))
    if any(s == "rss" for s in sources):
        results.append(discover_rss(RSS_FEEDS_DEFAULT))

    created = 0
    duplicates = 0
    errors: list[str] = []
    for res in results:
        errors.extend(res.errors)
        for item in res.items:
            _, was_created = pipeline_repo.upsert_opportunity(
                session, brand.id,
                source=item.source, source_id=item.source_id, topic=item.topic,
                url=item.url, published_at=item.published_at,
                engagement=item.engagement, trend=item.trend,
                raw_metadata=item.raw_metadata,
            )
            if was_created:
                created += 1
            else:
                duplicates += 1
    audit(session, action="pipeline.discover", outcome="OK",
          detail={"created": created, "duplicates": duplicates, "errors": errors})
    session.commit()
    return {"created": created, "duplicates": duplicates, "errors": errors}


@router.post("/research")
def research(req: ResearchRequest, session: Session = Depends(db_session)):
    from app.models.business import Opportunity

    opp = session.get(Opportunity, req.opportunity_id)
    if opp is None:
        raise HTTPException(404, "opportunity not found")
    item = pipeline_repo.save_research(
        session, req.opportunity_id,
        facts=req.facts, key_claims=req.key_claims, context=req.context,
        content_gaps=req.content_gaps, competition=req.competition,
        summary=req.summary, sources=req.sources, depth=req.depth,
    )
    audit(session, action="pipeline.research", entity_id=str(item.id), entity_type="research_item",
          detail={"sources": len(req.sources), "depth": req.depth})
    session.commit()
    return {"research_item_id": str(item.id), "opportunity_id": str(req.opportunity_id)}


@router.post("/score")
def score(req: ScoreOpportunityRequest, session: Session = Depends(db_session)):
    from app.engines.scoring import compute_score
    from app.models.business import Opportunity

    opp = session.get(Opportunity, req.opportunity_id)
    if opp is None:
        raise HTTPException(404, "opportunity not found")
    try:
        total, weighted, applied = compute_score(req.factors, req.penalties)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    last = (
        session.execute(
            select(OpportunityScore)
            .where(OpportunityScore.opportunity_id == opp.id)
            .order_by(OpportunityScore.version.desc())
        )
        .scalars()
        .first()
    )
    version = (last.version + 1) if last else 1
    row = OpportunityScore(opportunity_id=opp.id, version=version, factors=weighted,
                           penalties=applied, total=total)
    session.add(row)
    audit(session, action="pipeline.score", entity_id=str(opp.id), entity_type="opportunity",
          detail={"total": total, "version": version})
    session.commit()
    return {"opportunity_id": str(opp.id), "version": version, "total": total,
            "factors": weighted, "penalties": applied}


@router.post("/select")
def select_candidate(req: SelectRequest, session: Session = Depends(db_session)):
    from app.models.business import Opportunity

    opp = session.get(Opportunity, req.opportunity_id)
    if opp is None:
        raise HTTPException(404, "opportunity not found")

    is_dup, similarity, matched = pipeline_repo.check_duplicate_topic(session, opp.brand_id, req.title)
    if is_dup:
        audit(session, action="pipeline.select", entity_id=str(opp.id), outcome="REJECTED",
              detail={"reason": "DUPLICATE_TOPIC", "similarity": similarity, "matched": matched})
        session.commit()
        return {"selected": False, "reason": "DUPLICATE_TOPIC", "similarity": similarity,
                "matched": matched}

    if req.content_item_id:
        content = session.get(ContentItem, req.content_item_id)
        if content is None:
            raise HTTPException(404, "content item not found")
    else:
        content = pipeline_repo.create_content_item(
            session, opp.brand_id, title=req.title, opportunity_id=opp.id
        )
    # A fresh content item starts at DISCOVERED; the select endpoint consolidates
    # work already done at the opportunity level (research + scoring), so it walks
    # the legal path DISCOVERED -> RESEARCHING -> RESEARCHED -> SCORED -> SELECTED.
    if content.state == "DISCOVERED":
        transition_content(session, content, "RESEARCHING", reason="opportunity already researched")
        transition_content(session, content, "RESEARCHED", reason="research consolidated")
        transition_content(session, content, "SCORED", reason="opportunity already scored")
    transition_content(session, content, "SELECTED", reason="selected by scoring")
    audit(session, action="pipeline.select", entity_id=str(content.id), entity_type="content_item",
          outcome="OK", detail={"opportunity_id": str(opp.id), "similarity": similarity})
    session.commit()
    return {"selected": True, "content_item_id": str(content.id), "similarity": similarity}


@router.post("/strategy")
def create_strategy(req: StrategyRequest, session: Session = Depends(db_session)):
    content = session.get(ContentItem, req.content_item_id)
    if content is None:
        raise HTTPException(404, "content not found")
    _require_state(content, ["PLANNING", "SELECTED"])
    existing = session.execute(
        select(Strategy).where(Strategy.content_item_id == content.id)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(409, "strategy already exists for content item")
    row = Strategy(
        content_item_id=content.id, topic=req.topic, angle=req.angle, audience=req.audience,
        hook=req.hook, format=req.format, duration_seconds=req.duration_seconds,
        cta=req.cta, objective=req.objective, platforms=req.platforms,
    )
    session.add(row)
    if content.state == "SELECTED":
        transition_content(session, content, "PLANNING", reason="strategy created")
    audit(session, action="pipeline.strategy", entity_id=str(content.id), entity_type="strategy")
    session.commit()
    return {"strategy_id": str(row.id), "content_item_id": str(content.id)}


@router.post("/script")
def create_script(req: ScriptRequest, session: Session = Depends(db_session)):
    content = session.get(ContentItem, req.content_item_id)
    if content is None:
        raise HTTPException(404, "content not found")
    _require_state(content, ["PLANNING", "SCRIPTING"])

    # Budget check + cost record for LLM generation
    if req.cost_usd:
        try:
            spend_and_record(session, category="llm", amount=req.cost_usd,
                             content_item_id=content.id, detail={"stage": "script"})
        except Exception as exc:
            raise HTTPException(429, f"budget blocked: {exc}") from exc

    current = session.execute(select(Script).where(Script.content_item_id == content.id)).scalar_one_or_none()
    version = (current.current_version + 1) if current else 1
    if current is None:
        current = Script(content_item_id=content.id, current_version=0)
        session.add(current)
    full_text = "\n\n".join(
        f"[{k.upper()}]\n{v}" for k, v in req.sections.items() if str(k).upper() in
        {"HOOK", "CONTEXT", "CORE", "PAYOFF", "CTA"}
    )
    word_count = len((full_text or "").split())
    version_row = ScriptVersion(
        content_item_id=content.id, version=version, sections=req.sections,
        full_text=full_text, word_count=word_count, fact_check=req.fact_check,
        created_by=req.created_by,
    )
    session.add(version_row)
    current.current_version = version
    if content.state == "PLANNING":
        transition_content(session, content, "SCRIPTING", reason=f"script v{version}")
    audit(session, action="pipeline.script", entity_id=str(content.id), entity_type="script_version",
          detail={"version": version, "words": word_count})
    session.commit()
    return {"script_version_id": str(version_row.id), "version": version, "word_count": word_count}


@router.post("/produce")
def produce(req: ProduceVideoRequest, session: Session = Depends(db_session)):
    content = session.get(ContentItem, req.content_item_id)
    if content is None:
        raise HTTPException(404, "content not found")
    _require_state(content, ["SCRIPTING", "PRODUCING"])

    if req.cost_usd:
        try:
            spend_and_record(session, category="video", amount=req.cost_usd,
                             content_item_id=content.id,
                             detail={"stage": "video", "mpt_task_id": req.mpt_task_id})
        except Exception as exc:
            raise HTTPException(429, f"budget blocked: {exc}") from exc

    job = VideoJob(
        content_item_id=content.id, script_version_id=req.script_version_id,
        mpt_task_id=req.mpt_task_id, status="RENDERING", params=req.params,
    )
    session.add(job)
    if content.state == "SCRIPTING":
        transition_content(session, content, "PRODUCING", reason="video job submitted")
    audit(session, action="pipeline.produce", entity_id=str(job.id), entity_type="video_job",
          detail={"mpt_task_id": req.mpt_task_id})
    session.commit()
    return {"video_job_id": str(job.id), "content_item_id": str(content.id)}


@router.post("/produce/complete")
def produce_complete(req: VideoCompleteRequest, session: Session = Depends(db_session)):
    job = session.get(VideoJob, req.video_job_id)
    if job is None:
        raise HTTPException(404, "video job not found")
    content = session.get(ContentItem, job.content_item_id)
    if req.status == "COMPLETED":
        job.status = "COMPLETED"
        from app.models.base import now_utc

        job.completed_at = now_utc()
        for a in req.assets:
            session.add(Asset(
                content_item_id=job.content_item_id, asset_type=a.get("asset_type", "video"),
                storage_key=a["storage_key"], storage_uri=a["storage_uri"],
                checksum=a.get("checksum", ""), mime_type=a.get("mime_type", "video/mp4"),
                duration=a.get("duration"), size_bytes=a.get("size_bytes", 0),
                width=a.get("width"), height=a.get("height"), video_job_id=job.id,
            ))
        if content and content.state == "PRODUCING":
            transition_content(session, content, "QC", reason="video completed")
        outcome_detail = {"assets": len(req.assets)}
    else:
        job.status = "FAILED"
        job.error_code = req.error_code or "RENDER_FAILED"
        job.error_message = req.error_message
        if content and content.state == "PRODUCING":
            transition_content(session, content, "FAILED", reason="video render failed")
        outcome_detail = {"error_code": job.error_code}
    audit(session, action="pipeline.produce_complete", entity_id=str(job.id),
          entity_type="video_job", outcome="OK" if req.status == "COMPLETED" else "FAILED",
          detail=outcome_detail)
    session.commit()
    return {"video_job_id": str(job.id), "status": job.status}


@router.post("/produce/sync")
def produce_sync(req: ProduceSyncRequest, session: Session = Depends(db_session)):
    """Poll MPT for a submitted video job; on SUCCESS download the video and
    persist it to S3 (R2), record Assets, transition PRODUCING -> QC (§31/§18).

    This is the MPT -> storage bridge required by spec §19: business logic in
    FastAPI, orchestrators only call this endpoint.
    """
    job = session.get(VideoJob, req.video_job_id)
    if job is None:
        raise HTTPException(404, "video job not found")
    if job.status == "COMPLETED":
        return {"video_job_id": str(job.id), "status": "COMPLETED", "assets": job.assets_count
                if hasattr(job, "assets_count") else None}
    if not job.mpt_task_id:
        raise HTTPException(409, "video job has no mpt_task_id")

    mpt = _get_mpt_client()
    mpt._max_poll_seconds = req.poll_timeout_seconds  # bounded wait for this call
    try:
        result = mpt.wait_for_job(job.mpt_task_id)
    except Exception as exc:  # MPTError incl. TIMEOUT -> job stays RENDERING
        audit(session, action="pipeline.produce_sync", entity_id=str(job.id),
              entity_type="video_job", outcome="PENDING",
              detail={"reason": str(exc)[:200]})
        session.commit()
        raise HTTPException(202, f"MPT not finished: {exc}") from exc

    if result.status == "FAILED":
        job.status = "FAILED"
        job.error_code = "MPT_FAILED"
        job.error_message = "MPT task failed"
        content = session.get(ContentItem, job.content_item_id)
        if content and content.state == "PRODUCING":
            transition_content(session, content, "FAILED", reason="MPT render failed")
        audit(session, action="pipeline.produce_sync", entity_id=str(job.id),
              entity_type="video_job", outcome="FAILED", detail={"mpt": job.mpt_task_id})
        session.commit()
        return {"video_job_id": str(job.id), "status": "FAILED"}

    # SUCCESS: download primary video, upload to S3, record Asset
    import tempfile

    from app.models.base import now_utc

    storage = _get_storage()
    created = []
    with tempfile.TemporaryDirectory() as tmp:
        local = str(Path(tmp) / "final.mp4")
        mpt.download_result(result, local)
        key = f"videos/{job.content_item_id}/{job.id}/final.mp4"
        info = storage.put_file(local, key, metadata={"mpt_task_id": job.mpt_task_id})
        session.add(Asset(
            content_item_id=job.content_item_id, asset_type="video",
            storage_key=info["storage_key"], storage_uri=info["storage_uri"],
            checksum=info["checksum"], mime_type=info["mime_type"],
            size_bytes=info["size_bytes"], video_job_id=job.id,
        ))
        created.append(info["storage_key"])

    job.status = "COMPLETED"
    job.completed_at = now_utc()
    content = session.get(ContentItem, job.content_item_id)
    if content and content.state == "PRODUCING":
        transition_content(session, content, "QC", reason="video synced to storage")
    audit(session, action="pipeline.produce_sync", entity_id=str(job.id),
          entity_type="video_job", outcome="OK",
          detail={"assets": created, "mpt": job.mpt_task_id})
    session.commit()
    return {"video_job_id": str(job.id), "status": "COMPLETED", "assets": created}


@router.post("/qc")
def quality_control(req: QCRequest, session: Session = Depends(db_session)):
    content = session.get(ContentItem, req.content_item_id)
    if content is None:
        raise HTTPException(404, "content not found")
    _require_state(content, ["QC"])
    attempt_row = (
        session.execute(select(QCResult).where(QCResult.content_item_id == content.id)
                        .order_by(QCResult.attempt.desc()))
        .scalars().first()
    )
    attempt = (attempt_row.attempt + 1) if attempt_row else 1
    data = qc_engine.QCInput(
        video_exists=req.video_exists, file_readable=req.file_readable, duration=req.duration,
        expected_duration=req.expected_duration,
        resolution=tuple(req.resolution) if req.resolution else None,
        has_audio=req.has_audio, has_subtitle=req.has_subtitle,
        subtitle_aligns=req.subtitle_aligns, branding_ok=req.branding_ok,
        script_alignment_score=req.script_alignment_score, duplicate_risk=req.duplicate_risk,
        fact_risk=req.fact_risk,
        platform_constraint_violations=req.platform_constraint_violations,
    )
    verdict, score, checks = qc_engine.run_qc(data, threshold_auto=req.threshold_auto,
                                              threshold_review=req.threshold_review)
    row = QCResult(content_item_id=content.id, attempt=attempt, verdict=verdict, score=score,
                   checks=checks, threshold_auto=req.threshold_auto,
                   threshold_review=req.threshold_review)
    session.add(row)
    if verdict == "AUTO_APPROVED":
        transition_content(session, content, "READY", reason=f"QC auto-approved score={score}")
    elif verdict == "REVIEW_OR_REGENERATE":
        transition_content(session, content, "HUMAN_REVIEW", reason=f"QC score={score}")
        from app.models.business import ReviewQueue

        session.add(ReviewQueue(content_item_id=content.id, reason="QC", severity="MEDIUM",
                                payload={"score": float(score),
                                         "checks": {k: v["passed"] for k, v in checks.items()}}))
    else:
        transition_content(session, content, "REJECTED", reason=f"QC rejected score={score}")
    audit(session, action="pipeline.qc", entity_id=str(content.id), entity_type="qc_result",
          detail={"verdict": verdict, "score": float(score), "attempt": attempt})
    session.commit()
    return {"content_item_id": str(content.id), "verdict": verdict, "score": float(score),
            "checks": checks, "attempt": attempt}


@router.post("/adapt")
def adapt(req: AdaptRequest, session: Session = Depends(db_session)):
    content = session.get(ContentItem, req.content_item_id)
    if content is None:
        raise HTTPException(404, "content not found")
    _require_state(content, ["READY", "SCHEDULED", "PUBLISHING"])
    strategy = session.execute(
        select(Strategy).where(Strategy.content_item_id == content.id)
    ).scalar_one_or_none()
    hook = req.hook or (strategy.hook if strategy else "")
    title = req.title or content.title
    created: list[dict] = []
    for platform in req.platforms:
        try:
            payload = adaptation_engine.adapt_for_platform(
                platform, title=title, hook=hook, description=req.description,
                cta=req.cta, hashtags=req.hashtags,
            )
        except adaptation_engine.PlatformConstraintError as exc:
            raise HTTPException(422, str(exc)) from exc
        existing = session.execute(
            select(PlatformVariant).where(
                PlatformVariant.content_item_id == content.id,
                PlatformVariant.platform == platform,
            )
        ).scalar_one_or_none()
        if existing is None:
            variant = PlatformVariant(
                content_item_id=content.id, platform=platform, title=payload.get("title", ""),
                description=payload["description"], hashtags=payload["hashtags"],
                cta=payload.get("cta", ""), payload=payload,
            )
            session.add(variant)
            session.flush()
            created.append({"platform": platform, "variant_id": str(variant.id)})
        else:
            created.append({"platform": platform, "variant_id": str(existing.id), "existing": True})
    audit(session, action="pipeline.adapt", entity_id=str(content.id), entity_type="platform_variant",
          detail={"platforms": [c["platform"] for c in created]})
    session.commit()
    return {"variants": created}


@router.post("/publish")
def publish(req: PublishRequest, session: Session = Depends(db_session)):
    variant = session.get(PlatformVariant, req.variant_id)
    if variant is None:
        raise HTTPException(404, "variant not found")
    content = session.get(ContentItem, variant.content_item_id)

    settings = get_settings()
    safety = get_safety_state(session)
    allowed, reason = side_effect_allowed(safety.value, settings.dry_run)
    if not allowed and req.status == "PUBLISHED":
        audit(session, action="pipeline.publish", entity_id=str(variant.id),
              outcome="BLOCKED", detail={"reason": reason})
        session.commit()
        raise HTTPException(409, f"publish blocked: {reason}")

    job = session.execute(
        select(PublishJob).where(
            PublishJob.variant_id == variant.id,
            PublishJob.idempotency_key == req.idempotency_key,
        )
    ).scalar_one_or_none()

    if job is None:
        job = PublishJob(
            variant_id=variant.id, idempotency_key=req.idempotency_key, platform=variant.platform,
            status="PENDING",
        )
        session.add(job)
    # Idempotency: an existing PUBLISHED job for this key is never re-published.
    if job.status == "PUBLISHED":
        audit(session, action="pipeline.publish", entity_id=str(job.id), outcome="DUPLICATE_BLOCKED",
              detail={"idempotency_key": req.idempotency_key})
        session.commit()
        return {"publish_job_id": str(job.id), "status": "PUBLISHED", "idempotent_reuse": True}

    job.status = req.status
    job.platform_post_id = req.platform_post_id
    job.remote_url = req.remote_url
    job.attempts = (job.attempts or 0) + 1
    from app.models.base import now_utc

    job.last_attempt_at = now_utc()
    if req.status in ("PUBLISHED", "DRY_RUN"):
        job.published_at = now_utc()
    if req.status == "FAILED":
        job.error_code = req.error_code
        job.error_message = req.error_message

    if content is not None:
        if req.status == "PUBLISHED" and content.state in ("SCHEDULED", "PUBLISHING", "READY"):
            if content.state == "READY":
                transition_content(session, content, "SCHEDULED", reason="publishing")
            if content.state == "SCHEDULED":
                transition_content(session, content, "PUBLISHING", reason="publishing")
            transition_content(session, content, "PUBLISHED", reason="published " + variant.platform)

    audit(session, action="pipeline.publish", entity_id=str(job.id), entity_type="publish_job",
          outcome="OK" if req.status != "FAILED" else "FAILED",
          detail={"status": req.status, "platform": variant.platform})
    session.commit()
    return {"publish_job_id": str(job.id), "status": job.status, "idempotent_reuse": False}


def _require_state(content: ContentItem, allowed: list[str]) -> None:
    if content.state not in allowed:
        raise HTTPException(409, f"content state {content.state} not in {allowed}")
