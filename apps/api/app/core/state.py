"""Content lifecycle state machine (spec §43).

Every transition is validated and auditable. Illegal transitions raise
StateTransitionError and are never persisted.
"""
from __future__ import annotations

from enum import StrEnum


class ContentState(StrEnum):
    DISCOVERED = "DISCOVERED"
    RESEARCHING = "RESEARCHING"
    RESEARCHED = "RESEARCHED"
    SCORED = "SCORED"
    SELECTED = "SELECTED"
    PLANNING = "PLANNING"
    SCRIPTING = "SCRIPTING"
    PRODUCING = "PRODUCING"
    QC = "QC"
    READY = "READY"
    SCHEDULED = "SCHEDULED"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    MEASURING = "MEASURING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    HUMAN_REVIEW = "HUMAN_REVIEW"


TERMINAL_STATES = {ContentState.REJECTED, ContentState.FAILED, ContentState.COMPLETED}

# Allowed transitions. HUMAN_REVIEW may return to the productive state that
# raised it (resolution-driven), or resolve to REJECTED/FAILED.
ALLOWED_TRANSITIONS: dict[ContentState, set[ContentState]] = {
    ContentState.DISCOVERED: {ContentState.RESEARCHING, ContentState.REJECTED},
    ContentState.RESEARCHING: {ContentState.RESEARCHED, ContentState.FAILED, ContentState.HUMAN_REVIEW},
    ContentState.RESEARCHED: {ContentState.SCORED, ContentState.REJECTED},
    ContentState.SCORED: {ContentState.SELECTED, ContentState.REJECTED},
    ContentState.SELECTED: {ContentState.PLANNING, ContentState.REJECTED},
    ContentState.PLANNING: {ContentState.SCRIPTING, ContentState.REJECTED, ContentState.HUMAN_REVIEW},
    ContentState.SCRIPTING: {ContentState.PRODUCING, ContentState.FAILED, ContentState.HUMAN_REVIEW},
    ContentState.PRODUCING: {ContentState.QC, ContentState.FAILED},
    ContentState.QC: {ContentState.READY, ContentState.REJECTED, ContentState.HUMAN_REVIEW},
    ContentState.READY: {ContentState.SCHEDULED, ContentState.PRODUCING},
    ContentState.SCHEDULED: {ContentState.PUBLISHING, ContentState.READY},
    ContentState.PUBLISHING: {
        ContentState.PUBLISHED,
        ContentState.FAILED,
        ContentState.HUMAN_REVIEW,
    },
    ContentState.PUBLISHED: {ContentState.MEASURING},
    ContentState.MEASURING: {ContentState.COMPLETED},
    ContentState.HUMAN_REVIEW: {
        # resolution paths decided by reviewer
        ContentState.PLANNING,
        ContentState.SCRIPTING,
        ContentState.PRODUCING,
        ContentState.READY,
        ContentState.PUBLISHING,
        ContentState.REJECTED,
        ContentState.FAILED,
    },
    ContentState.REJECTED: set(),
    ContentState.FAILED: {ContentState.PRODUCING},  # explicit retry of production
    ContentState.COMPLETED: set(),
}


class StateTransitionError(Exception):
    def __init__(self, from_state: str, to_state: str):
        self.from_state = from_state
        self.to_state = to_state
        super().__init__(f"Illegal content state transition: {from_state} -> {to_state}")


def validate_transition(from_state: str | ContentState, to_state: str | ContentState) -> None:
    """Raise StateTransitionError unless from_state -> to_state is allowed."""
    src = ContentState(from_state)
    dst = ContentState(to_state)
    if dst not in ALLOWED_TRANSITIONS.get(src, set()):
        raise StateTransitionError(str(src), str(dst))
