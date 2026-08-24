"""State machine tests (spec §43, §56)."""
import pytest

from app.core.state import (
    ALLOWED_TRANSITIONS,
    ContentState,
    StateTransitionError,
    validate_transition,
)


def test_happy_path_transitions():
    path = [
        "DISCOVERED", "RESEARCHING", "RESEARCHED", "SCORED", "SELECTED", "PLANNING",
        "SCRIPTING", "PRODUCING", "QC", "READY", "SCHEDULED", "PUBLISHING", "PUBLISHED",
        "MEASURING", "COMPLETED",
    ]
    for a, b in zip(path, path[1:], strict=False):
        validate_transition(a, b)  # must not raise


def test_illegal_skip():
    with pytest.raises(StateTransitionError):
        validate_transition("DISCOVERED", "PUBLISHED")
    with pytest.raises(StateTransitionError):
        validate_transition("SCORED", "PRODUCING")


def test_terminal_states_have_no_exits():
    for terminal in ("REJECTED", "COMPLETED"):
        assert ALLOWED_TRANSITIONS[ContentState(terminal)] == set()
    # FAILED allows exactly one retry path: back to PRODUCING
    assert ALLOWED_TRANSITIONS[ContentState.FAILED] == {ContentState.PRODUCING}


def test_rejected_is_absorbing():
    with pytest.raises(StateTransitionError):
        validate_transition("REJECTED", "DISCOVERED")


def test_human_review_paths():
    validate_transition("QC", "HUMAN_REVIEW")
    validate_transition("HUMAN_REVIEW", "REJECTED")
    validate_transition("HUMAN_REVIEW", "PRODUCING")
    with pytest.raises(StateTransitionError):
        validate_transition("HUMAN_REVIEW", "PUBLISHED")
