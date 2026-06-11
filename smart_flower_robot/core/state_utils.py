"""
core/state_utils.py
===================
Generic utilities for state management and goal checking.
"""

from __future__ import annotations

from core.models import State

class StateCounter:
    """Thread-safe-ish auto-incrementing counter for state IDs."""

    def __init__(self, start: int = 1):
        self._value = start

    def next(self) -> int:
        val = self._value
        self._value += 1
        return val


def is_goal_state(state: State) -> bool:
    """Return True when:
        1. All pavilion needs are fully satisfied (remaining == 0).
        2. The robot carries no bouquets.
    """
    if state.load_total() > 0:
        return False
    for qty in state.remaining_needs.values():
        if qty > 0:
            return False
    return True


def state_signature(state: State) -> tuple:
    """Delegates to State.signature() for a hashable, comparable key."""
    return state.signature()
