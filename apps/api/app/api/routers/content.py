"""Content items API: list, get, state transitions, pipeline stats."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.state import ALLOWED_TRANSITIONS, StateTransitionError
from app.models.business import ContentItem
from app.schemas.api import ContentItemOut, TransitionRequest
from app.services.state_service import transition_content

router = APIRouter(prefix="/content", tags=["content"])


@router.get("", response_model=list[ContentItemOut])
def list_content(
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: Session = Depends(db_session),
):
    stmt = select(ContentItem).order_by(ContentItem.created_at.desc()).limit(min(limit, 200)).offset(offset)
    if state:
        stmt = stmt.where(ContentItem.state == state)
    return list(session.execute(stmt).scalars().all())


@router.get("/stats")
def content_stats(session: Session = Depends(db_session)):
    rows = session.execute(
        select(ContentItem.state, func.count(ContentItem.id)).group_by(ContentItem.state)
    ).all()
    return {"by_state": {state: count for state, count in rows}}


@router.get("/states")
def list_states():
    return {
        "states": sorted(ALLOWED_TRANSITIONS.keys()),
        "transitions": {k.value: sorted(v.value for v in vals) for k, vals in ALLOWED_TRANSITIONS.items()},
    }


@router.get("/{content_id}", response_model=ContentItemOut)
def get_content(content_id: uuid.UUID, session: Session = Depends(db_session)):
    obj = session.get(ContentItem, content_id)
    if obj is None:
        raise HTTPException(404, "content not found")
    return obj


@router.post("/{content_id}/transition")
def transition(content_id: uuid.UUID, payload: TransitionRequest,
               session: Session = Depends(db_session)):
    obj = session.get(ContentItem, content_id)
    if obj is None:
        raise HTTPException(404, "content not found")
    try:
        transition_content(session, obj, payload.to_state, reason=payload.reason)
    except StateTransitionError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from exc
    session.commit()
    return {"id": str(obj.id), "state": obj.state, "history": obj.state_history[-3:]}
