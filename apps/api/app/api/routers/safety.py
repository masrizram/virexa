"""Safety state API (spec §53): RUNNING / PAUSED / EMERGENCY_STOP."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.core.safety import SafetyState
from app.schemas.api import SafetyRequest
from app.services.state_service import audit, get_safety_state, set_safety_state

router = APIRouter(prefix="/safety", tags=["safety"])


@router.get("")
def get_safety(session: Session = Depends(db_session)):
    state = get_safety_state(session)
    return {"state": state.value}


@router.post("")
def set_safety(payload: SafetyRequest, session: Session = Depends(db_session)):
    state = SafetyState(payload.state)
    set_safety_state(session, state, actor="operator-api")
    session.commit()
    return {"state": state.value}
