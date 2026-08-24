"""Cost engine (spec §41) + budget guard (spec §42).

Costs are recorded as cost_events rows; budgets enforced per UTC day.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.safety import BudgetExceededError
from app.models.business import CostEvent
from app.services.state_service import get_setting

BUDGETS_KEY = "budgets"


def record_cost(session: Session, *, category: str, amount: float, currency: str = "USD",
                content_item_id: uuid.UUID | None = None, workflow_run_id: str = "",
                detail: dict | None = None) -> CostEvent:
    event = CostEvent(
        category=category,
        amount=round(float(amount), 6),
        currency=currency,
        content_item_id=content_item_id,
        workflow_run_id=workflow_run_id,
        detail=detail or {},
    )
    session.add(event)
    return event


def spent_today(session: Session, *, category: str | None = None) -> float:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.coalesce(func.sum(CostEvent.amount), 0.0)).where(
        CostEvent.created_at >= start
    )
    if category:
        stmt = stmt.where(CostEvent.category == category)
    return float(session.execute(stmt).scalar_one())


def content_count_today(session: Session) -> int:
    """Videos generated today = completed video jobs; proxied via cost_events category=video rows."""
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(CostEvent.id)).where(
        and_(CostEvent.category == "video", CostEvent.created_at >= start)
    )
    return int(session.execute(stmt).scalar_one())


def get_budgets(session: Session) -> dict:
    value = get_setting(session, BUDGETS_KEY)
    from app.core.safety import BUDGET_DEFAULTS

    merged = dict(BUDGET_DEFAULTS)
    if value:
        merged.update({k: v for k, v in value.items() if k in BUDGET_DEFAULTS})
    return merged


def check_budget(session: Session, *, category: str, amount: float = 0.0) -> None:
    """Raise BudgetExceededError if recording `amount` under `category` would exceed today's budget.

    Also enforces daily content limit when category == 'video'.
    """
    budgets = get_budgets(session)
    total_spent = spent_today(session)
    total_limit = float(budgets.get("daily_total_budget", 0))
    if total_limit > 0 and total_spent + amount > total_limit:
        raise BudgetExceededError("daily_total_budget", round(total_spent, 4), total_limit)

    if category == "llm":
        limit = float(budgets.get("daily_llm_budget", 0))
        spent = spent_today(session, category="llm")
        if limit > 0 and spent + amount > limit:
            raise BudgetExceededError("daily_llm_budget", round(spent, 4), limit)
    elif category == "video":
        limit = float(budgets.get("daily_video_budget", 0))
        spent = spent_today(session, category="video")
        if limit > 0 and spent + amount > limit:
            raise BudgetExceededError("daily_video_budget", round(spent, 4), limit)
        content_limit = int(float(budgets.get("daily_content_limit", 0)))
        if content_limit > 0:
            count = content_count_today(session)
            if count >= content_limit:
                raise BudgetExceededError("daily_content_limit", float(count), float(content_limit))


def spend_and_record(session: Session, *, category: str, amount: float,
                     content_item_id: uuid.UUID | None = None, workflow_run_id: str = "",
                     detail: dict | None = None) -> CostEvent:
    check_budget(session, category=category, amount=amount)
    return record_cost(session, category=category, amount=amount, content_item_id=content_item_id,
                       workflow_run_id=workflow_run_id, detail=detail)
