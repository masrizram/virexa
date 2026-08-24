"""Human review queue API (spec §52)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.models.business import ReviewQueue
from app.schemas.api import ReviewActionRequest
from app.services.state_service import audit

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
def list_reviews(status: str = "PENDING", limit: int = 100,
                 session: Session = Depends(db_session)):
    rows = session.execute(
        select(ReviewQueue)
        .where(ReviewQueue.status == status)
        .order_by(ReviewQueue.created_at.desc())
        .limit(min(limit, 500))
    ).scalars().all()
    return [
        {
            "id": str(r.id),
            "content_item_id": str(r.content_item_id) if r.content_item_id else None,
            "interaction_id": str(r.interaction_id) if r.interaction_id else None,
            "reason": r.reason,
            "severity": r.severity,
            "status": r.status,
            "payload": r.payload,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.post("/{review_id}/resolve")
def resolve_review(review_id: uuid.UUID, payload: ReviewActionRequest,
                   session: Session = Depends(db_session)):
    row = session.get(ReviewQueue, review_id)
    if row is None:
        raise HTTPException(404, "review not found")
    if row.status != "PENDING":
        raise HTTPException(409, f"review already {row.status}")
    row.status = "RESOLVED"
    row.resolution = payload.action
    row.resolved_by = payload.actor
    from app.models.base import now_utc

    row.resolved_at = now_utc()
    audit(
        session,
        action="review.resolve",
        entity_type="review_queue",
        entity_id=str(row.id),
        actor=payload.actor,
        detail={"action": payload.action, "note": payload.note, "reason": row.reason},
    )
    session.commit()
    return {"id": str(row.id), "status": row.status, "resolution": row.resolution}
