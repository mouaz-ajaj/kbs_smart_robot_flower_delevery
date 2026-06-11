"""
core/validators.py
==================
Pure validation functions used by both the expert-system rules and
the procedural search code.

Every function is a *predicate* – it returns True / False (or a
descriptive string for rejection reasons) without side effects.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from core.models import Pavilion, Position, Problem, State


# ═══════════════════════════════════════════════════════════════════════════════
#  Grid / position checks
# ═══════════════════════════════════════════════════════════════════════════════

def is_inside_grid(position: Position, problem: Problem) -> bool:
    """Return True if *position* is within the grid boundaries (1-indexed)."""
    return (
        1 <= position.x <= problem.grid_width
        and 1 <= position.y <= problem.grid_height
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Flower / color checks
# ═══════════════════════════════════════════════════════════════════════════════

def is_valid_flower_color(
    flower_type: str, color: str, problem: Problem
) -> bool:
    """Return True if *color* is a valid color for *flower_type*."""
    return (
        flower_type in problem.flowers
        and color in problem.flowers[flower_type]
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Load-pattern checks  (apply to any load dictionary: batch or total cargo)
# ═══════════════════════════════════════════════════════════════════════════════

def merge_loads(
    current_load: Dict[Tuple[str, str], int],
    new_batch: Dict[Tuple[str, str], int]
) -> Dict[Tuple[str, str], int]:
    """Return a new dictionary representing the combined load."""
    combined = dict(current_load)
    for k, v in new_batch.items():
        combined[k] = combined.get(k, 0) + v
    return combined


def is_valid_load_pattern(load_batch: Dict[Tuple[str, str], int]) -> bool:
    """Check that all items in a proposed load satisfy either:
        Option A – all items share the same **color** (different types OK), or
        Option B – all items share the same **flower type** (different colors OK).

    Applies to any load dictionary (a single batch or the total cargo).
    Returns True if the pattern is valid.

    Examples:
        - {("Rose","Red"): 1, ("Tulip","Yellow"): 1} -> False
        - {("Rose","Red"): 1, ("Rose","Pink"): 1} -> True
        - {("Rose","Red"): 1, ("Tulip","Red"): 1} -> True
    """
    if len(load_batch) <= 1:
        return True

    types = set(ft for ft, _ in load_batch.keys())
    colors = set(c for _, c in load_batch.keys())

    # Option A: same color  OR  Option B: same type
    return len(colors) == 1 or len(types) == 1


def is_over_max_load(
    current_load: Dict[Tuple[str, str], int],
    new_batch: Dict[Tuple[str, str], int],
    problem: Problem,
) -> bool:
    """Return True if adding *new_batch* to *current_load* would exceed
    the robot's max_load capacity."""
    current_total = sum(current_load.values())
    batch_total = sum(new_batch.values())
    return (current_total + batch_total) > problem.max_load


def load_batch_is_needed(
    load_batch: Dict[Tuple[str, str], int],
    remaining_needs: Dict[Tuple[str, str], int],
    problem: Problem,
) -> bool:
    """Return True if every (type, color) in the batch is still needed
    by at least one pavilion whose type matches."""
    for (ft, color), qty in load_batch.items():
        # Find at least one pavilion of this type needing this color
        found = False
        for pav in problem.pavilions:
            if pav.type == ft:
                rem = remaining_needs.get((pav.id, color), 0)
                if rem > 0:
                    found = True
                    break
        if not found:
            return False
    return True


# ═══════════════════════════════════════════════════════════════════════════════
#  Unload checks
# ═══════════════════════════════════════════════════════════════════════════════

def matches_pavilion_type(
    bouquet_type: str, pavilion: Pavilion
) -> bool:
    """Return True if a bouquet's flower type matches the pavilion's type."""
    return bouquet_type == pavilion.type


def can_unload_color_at_pavilion(
    state: State, pavilion: Pavilion, color: str
) -> bool:
    """Return True if the robot can unload *color* at *pavilion*.

    Conditions:
        1. The pavilion's flower type must match the bouquet type.
        2. The pavilion must still need that color (remaining > 0).
        3. The robot must carry **at least** the remaining need for
           that color (partial unloading is forbidden).
    """
    remaining = state.remaining_needs.get((pavilion.id, color), 0)
    if remaining <= 0:
        return False

    carried = state.load.get((pavilion.type, color), 0)
    return carried >= remaining


def can_unload_at_pavilion(
    state: State, pavilion: Pavilion
) -> bool:
    """Return True if any color can be unloaded at *pavilion*."""
    for color in pavilion.needs:
        if can_unload_color_at_pavilion(state, pavilion, color):
            return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
#  Goal check
# ═══════════════════════════════════════════════════════════════════════════════

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


# ═══════════════════════════════════════════════════════════════════════════════
#  State signature  (convenience wrapper)
# ═══════════════════════════════════════════════════════════════════════════════

def state_signature(state: State) -> tuple:
    """Delegates to State.signature() for a hashable, comparable key."""
    return state.signature()


# ═══════════════════════════════════════════════════════════════════════════════
#  Rejection-reason helpers
# ═══════════════════════════════════════════════════════════════════════════════

def validate_move(
    new_pos: Position, problem: Problem
) -> Optional[str]:
    """Return a rejection reason string, or None if the move is valid."""
    if not is_inside_grid(new_pos, problem):
        return f"Position {new_pos} is outside the grid."
    return None


def validate_load_batch(
    state: State,
    load_batch: Dict[Tuple[str, str], int],
    problem: Problem,
) -> Optional[str]:
    """Return a rejection reason string, or None if the load is valid."""
    if state.robot_pos != problem.warehouse:
        return "Robot is not at the warehouse."

    for qty in load_batch.values():
        if qty <= 0:
            return "Load quantities must be positive."

    combined_load = merge_loads(state.load, load_batch)

    if not is_valid_load_pattern(combined_load):
        return "Total robot load violates pattern constraint (must be same-color or same-type)."

    if is_over_max_load(state.load, load_batch, problem):
        return "Load would exceed max_load capacity."

    if not load_batch_is_needed(load_batch, state.remaining_needs, problem):
        return "Load contains bouquets not needed by any pavilion."

    return None
