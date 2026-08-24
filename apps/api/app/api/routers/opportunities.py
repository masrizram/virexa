"""Opportunities API."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.engines.scoring import compute_score
from app.models.business import Opportunity, OpportunityScore
from app.schemas.api import OpportunityOut, ScoreRequest

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


@router.get("", response_model=list[OpportunityOut])
def list_opportunities(
    limit: int = 50,
    offset: int = 0,
    source: str | None = None,
    session: Session = Depends(db_session),
):
    stmt = (
        select(Opportunity)
        .order_by(Opportunity.discovered_at.desc())
        .limit(min(limit, 200))
        .offset(offset)
    )
    if source:
        stmt = stmt.where(Opportunity.source == source)
    return list(session.execute(stmt).scalars().all())


@router.get("/{opportunity_id}", response_model=OpportunityOut)
def get_opportunity(opportunity_id: uuid.UUID, session: Session = Depends(db_session)):
    obj = session.get(Opportunity, opportunity_id)
    if obj is None:
        raise HTTPException(404, "opportunity not found")
    return obj


@router.post("/{opportunity_id}/score")
def score_opportunity(opportunity_id: uuid.UUID, payload: ScoreRequest,
                      session: Session = Depends(db_session)):
    if payload.opportunity_id != opportunity_id:
        raise HTTPException(422, "path id and body opportunity_id must match")
    obj = session.get(Opportunity, opportunity_id)
    if obj is None:
        raise HTTPException(404, "opportunity not found")
    try:
        total, weighted, applied = compute_score(payload.factors, payload.penalties)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    last = (
        session.execute(
            select(OpportunityScore)
            .where(OpportunityScore.opportunity_id == obj.id)
            .order_by(OpportunityScore.version.desc())
        )
        .scalars()
        .first()
    )
    version = (last.version + 1) if last else 1
    row = OpportunityScore(
        opportunity_id=obj.id,
        version=version,
        factors=weighted,
        penalties=applied,
        total=total,
    )
    session.add(row)
    session.commit()
    return {
        "opportunity_id": str(obj.id),
        "version": version,
        "total": total,
        "factors": weighted,
        "penalties": applied,
    }
