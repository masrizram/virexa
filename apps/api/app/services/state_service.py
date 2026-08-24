"""Audited content state transitions + system settings + safety state access."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.safety import SAFETY_SETTINGS_KEY, SafetyState
from app.core.state import ContentState, validate_transition
from app.models.base import now_utc
from app.models.business import AuditEvent, ContentItem, SystemSetting

DEFAULTS_KEY = "budgets"
SCORING_KEY = "scoring"
QC_KEY = "qc"


def audit(
    session: Session,
    *,
    action: str,
    entity_type: str = "",
    entity_id: str = "",
    outcome: str = "OK",
    actor: str = "system",
    detail: dict | None = None,
) -> AuditEvent:
    event = AuditEvent(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        outcome=outcome,
        detail=detail or {},
    )
    session.add(event)
    return event


def transition_content(
    session: Session,
    content: ContentItem,
    to_state: str,
    *,
    actor: str = "system",
    reason: str = "",
) -> ContentItem:
    """Validate + persist a state transition with full audit trail (spec §43)."""
    validate_transition(content.state, to_state)
    from_state = content.state
    content.state = ContentState(to_state).value
    entry = {
        "from": from_state,
        "to": to_state,
        "at": now_utc().isoformat(),
        "actor": actor,
        "reason": reason,
    }
    history = list(content.state_history or [])
    history.append(entry)
    content.state_history = history
    if to_state == ContentState.HUMAN_REVIEW.value:
        content.human_review_required = True
    session.add(content)
    audit(
        session,
        action="content.transition",
        entity_type="content_item",
        entity_id=str(content.id),
        actor=actor,
        detail={"from": from_state, "to": to_state, "reason": reason},
    )
    return content


def get_setting(session: Session, key: str) -> dict | None:
    row = session.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    return row.value if row else None


def set_setting(session: Session, key: str, value: dict, description: str = "") -> SystemSetting:
    row = session.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        row = SystemSetting(key=key, value=value, description=description)
        session.add(row)
    else:
        row.value = value
    return row


def get_safety_state(session: Session) -> SafetyState:
    value = get_setting(session, SAFETY_SETTINGS_KEY)
    if not value:
        return SafetyState.RUNNING
    return SafetyState(value.get("state", SafetyState.RUNNING.value))


def set_safety_state(session: Session, state: SafetyState, actor: str = "operator") -> None:
    set_setting(session, SAFETY_SETTINGS_KEY, {"state": state.value, "updated_at": now_utc().isoformat()})
    audit(session, action="safety.state", entity_type="system_setting", entity_id=SAFETY_SETTINGS_KEY,
          actor=actor, detail={"state": state.value})
