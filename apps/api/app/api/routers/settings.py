"""System settings API: budgets, scoring weights, QC thresholds."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import db_session
from app.schemas.api import BudgetUpdateRequest
from app.services.cost_service import BUDGETS_KEY, get_budgets, spent_today
from app.services.state_service import audit, set_setting

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/budgets")
def budgets(session: Session = Depends(db_session)):
    return {
        "budgets": get_budgets(session),
        "spent_today": {
            "llm": spent_today(session, category="llm"),
            "video": spent_today(session, category="video"),
            "total": spent_today(session),
        },
    }


@router.post("/budgets")
def update_budgets(payload: BudgetUpdateRequest, session: Session = Depends(db_session)):
    current = get_budgets(session)
    merged = dict(current)
    merged.update({k: v for k, v in payload.budgets.items() if k in current})
    set_setting(session, BUDGETS_KEY, merged, description="daily budget limits")
    audit(session, action="settings.budgets", entity_type="system_setting", entity_id=BUDGETS_KEY,
          actor="operator-api", detail={"updated": payload.budgets})
    session.commit()
    return {"budgets": merged}
