"""
core/actions.py
===============
Successor-state generation for the Smart Flower Robot.

Each ``generate_*`` function takes the current State (and Problem) and returns
a list of new State objects (or load-dicts / unload-specs) that represent
valid transitions.

This module is the *workhorse* called by the Experta rules and by the
procedural A* loop in ``core/search.py``.
"""

from __future__ import annotations

import itertools
from copy import deepcopy
from typing import Dict, List, Tuple

from core.heuristics import heuristic
from core.models import Action, Pavilion, Position, Problem, RejectedRecord, State
from core.validators import (
    can_unload_color_at_pavilion,
    is_inside_grid,
    is_over_max_load,
    is_valid_load_pattern,
    load_batch_is_needed,
    validate_load_batch,
    validate_move,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  State-ID counter
# ═══════════════════════════════════════════════════════════════════════════════

class StateCounter:
    """Thread-safe-ish auto-incrementing counter for state IDs."""

    def __init__(self, start: int = 1):
        self._value = start

    def next(self) -> int:
        val = self._value
        self._value += 1
        return val


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers to build child states
# ═══════════════════════════════════════════════════════════════════════════════

def _make_child(
    parent: State,
    robot_pos: Position,
    load: Dict[Tuple[str, str], int],
    remaining_needs: Dict[Tuple[str, str], int],
    action_name: str,
    action_desc: str,
    problem: Problem,
    counter: StateCounter,
) -> State:
    """Create a child State from *parent* with the given changes."""
    new_id = counter.next()
    g = parent.g + 1
    h = heuristic(
        robot_pos, load, remaining_needs, problem
    )
    act = Action(name=action_name, description=action_desc)
    return State(
        id=new_id,
        robot_pos=robot_pos,
        load=load,
        remaining_needs=remaining_needs,
        g=g,
        h=h,
        f=g + h,
        path=parent.path + [act],
        parent_id=parent.id,
        action=action_desc,
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Movement generators
# ═══════════════════════════════════════════════════════════════════════════════

def generate_move_right(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[State | None, RejectedRecord | None]:
    new_pos = Position(state.robot_pos.x + 1, state.robot_pos.y)
    reason = validate_move(new_pos, problem)
    if reason:
        return None, RejectedRecord(state.id, "Move Right", reason)
    desc = f"Move Right -> robot at {new_pos}"
    child = _make_child(
        state, new_pos, dict(state.load), dict(state.remaining_needs),
        "Move Right", desc, problem, counter,
    )
    return child, None


def generate_move_left(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[State | None, RejectedRecord | None]:
    new_pos = Position(state.robot_pos.x - 1, state.robot_pos.y)
    reason = validate_move(new_pos, problem)
    if reason:
        return None, RejectedRecord(state.id, "Move Left", reason)
    desc = f"Move Left -> robot at {new_pos}"
    child = _make_child(
        state, new_pos, dict(state.load), dict(state.remaining_needs),
        "Move Left", desc, problem, counter,
    )
    return child, None


def generate_move_up(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[State | None, RejectedRecord | None]:
    new_pos = Position(state.robot_pos.x, state.robot_pos.y - 1)
    reason = validate_move(new_pos, problem)
    if reason:
        return None, RejectedRecord(state.id, "Move Up", reason)
    desc = f"Move Up -> robot at {new_pos}"
    child = _make_child(
        state, new_pos, dict(state.load), dict(state.remaining_needs),
        "Move Up", desc, problem, counter,
    )
    return child, None


def generate_move_down(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[State | None, RejectedRecord | None]:
    new_pos = Position(state.robot_pos.x, state.robot_pos.y + 1)
    reason = validate_move(new_pos, problem)
    if reason:
        return None, RejectedRecord(state.id, "Move Down", reason)
    desc = f"Move Down -> robot at {new_pos}"
    child = _make_child(
        state, new_pos, dict(state.load), dict(state.remaining_needs),
        "Move Down", desc, problem, counter,
    )
    return child, None


def generate_moves(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[List[State], List[RejectedRecord]]:
    """Generate all valid move actions from the current state."""
    children: List[State] = []
    rejected: List[RejectedRecord] = []

    for gen_fn in (
        generate_move_right,
        generate_move_left,
        generate_move_up,
        generate_move_down,
    ):
        child, rej = gen_fn(state, problem, counter)
        if child is not None:
            children.append(child)
        if rej is not None:
            rejected.append(rej)

    return children, rejected


# ═══════════════════════════════════════════════════════════════════════════════
#  Load generators
# ═══════════════════════════════════════════════════════════════════════════════

def _format_load_batch(batch: Dict[Tuple[str, str], int]) -> str:
    items = sorted(batch.items())
    return "[" + ", ".join(f"{ft} {c} x{q}" for (ft, c), q in items) + "]"


def _positive_subset_sums(values: List[int]) -> List[int]:
    """Return all unique positive subset sums from a list of values."""
    if not values:
        return []
    sums = set()
    for r in range(1, len(values) + 1):
        for subset in itertools.combinations(values, r):
            s = sum(subset)
            if s > 0:
                sums.add(s)
    return sorted(list(sums))


def _deduplicate_batches(batches: List[Dict[Tuple[str, str], int]]) -> List[Dict[Tuple[str, str], int]]:
    """Remove duplicates from a list of batches."""
    seen = set()
    unique = []
    for b in batches:
        sig = frozenset(b.items())
        if sig not in seen:
            seen.add(sig)
            unique.append(b)
    return unique


def generate_same_type_loads(
    state: State, problem: Problem
) -> List[Dict[Tuple[str, str], int]]:
    """Option B -- same flower type, different colors allowed."""
    results: List[Dict[Tuple[str, str], int]] = []
    current_total = state.load_total()
    capacity = problem.max_load - current_total
    if capacity <= 0:
        return results

    for flower_type in problem.flowers:
        # Group remaining needs by color for this flower type
        color_to_needs: Dict[str, List[int]] = {}
        for pav in problem.pavilions:
            if pav.type == flower_type:
                for color in pav.needs:
                    rem = state.remaining_needs.get((pav.id, color), 0)
                    if rem > 0:
                        color_to_needs.setdefault(color, []).append(rem)
                        
        if not color_to_needs:
            continue
            
        # For each color, get all possible subset sums
        color_possible_quantities: Dict[str, List[int]] = {}
        for color, needs_list in color_to_needs.items():
            color_possible_quantities[color] = _positive_subset_sums(needs_list)
            
        colors = list(color_possible_quantities.keys())
        
        # Generate combinations of colors (from size 1 to len(colors))
        for r in range(1, len(colors) + 1):
            for color_combo in itertools.combinations(colors, r):
                # For this combination, pick one possible quantity per color using product
                quantities_lists = [color_possible_quantities[c] for c in color_combo]
                for qty_combo in itertools.product(*quantities_lists):
                    total = sum(qty_combo)
                    if total > 0 and total <= capacity:
                        batch = {}
                        for c, q in zip(color_combo, qty_combo):
                            batch[(flower_type, c)] = q
                        results.append(batch)

    return _deduplicate_batches(results)


def generate_same_color_loads(
    state: State, problem: Problem
) -> List[Dict[Tuple[str, str], int]]:
    """Option A – same color, different flower types allowed."""
    results: List[Dict[Tuple[str, str], int]] = []
    current_total = state.load_total()
    capacity = problem.max_load - current_total
    if capacity <= 0:
        return results

    # Collect all possible colors
    all_colors = set()
    for pav in problem.pavilions:
        all_colors.update(pav.needs)
        
    for color in all_colors:
        # Group remaining needs by flower_type for this color
        type_to_needs: Dict[str, List[int]] = {}
        for pav in problem.pavilions:
            rem = state.remaining_needs.get((pav.id, color), 0)
            if rem > 0:
                type_to_needs.setdefault(pav.type, []).append(rem)
                
        if len(type_to_needs) < 2:
            continue
            
        # For each flower type, get all possible subset sums
        type_possible_quantities: Dict[str, List[int]] = {}
        for ft, needs_list in type_to_needs.items():
            type_possible_quantities[ft] = _positive_subset_sums(needs_list)
            
        types = list(type_possible_quantities.keys())
        
        # Generate combinations of flower types (size >= 2)
        for r in range(2, len(types) + 1):
            for type_combo in itertools.combinations(types, r):
                quantities_lists = [type_possible_quantities[ft] for ft in type_combo]
                for qty_combo in itertools.product(*quantities_lists):
                    total = sum(qty_combo)
                    if total > 0 and total <= capacity:
                        batch = {}
                        for ft, q in zip(type_combo, qty_combo):
                            batch[(ft, color)] = q
                        results.append(batch)

    return _deduplicate_batches(results)


def generate_loads(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[List[State], List[RejectedRecord]]:
    """Generate all valid load actions at the warehouse.

    Returns (children, rejected).
    """
    children: List[State] = []
    rejected: List[RejectedRecord] = []

    if state.robot_pos != problem.warehouse:
        return children, rejected

    # Collect candidate batches
    batches_raw = generate_same_type_loads(state, problem)
    batches_raw.extend(generate_same_color_loads(state, problem))

    # Deduplicate batches
    batches = _deduplicate_batches(batches_raw)

    # Convert valid batches into child states
    for batch in batches:
        reason = validate_load_batch(state, batch, problem)
        if reason:
            rejected.append(
                RejectedRecord(state.id, f"Load {_format_load_batch(batch)}", reason)
            )
            continue

        new_load = dict(state.load)
        for key, qty in batch.items():
            new_load[key] = new_load.get(key, 0) + qty

        desc = f"Load {_format_load_batch(batch)}"
        child = _make_child(
            state,
            state.robot_pos,
            new_load,
            dict(state.remaining_needs),
            "Load",
            desc,
            problem,
            counter,
        )
        children.append(child)

    return children, rejected


# ═══════════════════════════════════════════════════════════════════════════════
#  Unload generators
# ═══════════════════════════════════════════════════════════════════════════════

def _find_pavilion_at(pos: Position, problem: Problem) -> Pavilion | None:
    """Return the Pavilion at *pos*, or None."""
    for pav in problem.pavilions:
        if pav.position == pos:
            return pav
    return None


def generate_unloads(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[List[State], List[RejectedRecord]]:
    """Generate valid unload actions at the current position.

    Rules:
        - Only at a pavilion.
        - Only bouquets whose type matches the pavilion.
        - A color is unloaded ONLY if carried qty ≥ remaining need (no partial).
        - Multiple eligible colors can be unloaded together (cost = 1).
        - Generates all non-empty subsets of eligible colors so A* can choose.
    """
    children: List[State] = []
    rejected: List[RejectedRecord] = []

    pavilion = _find_pavilion_at(state.robot_pos, problem)
    if pavilion is None:
        return children, rejected

    # Find colors eligible for unloading
    eligible_colors: List[str] = []
    for color in pavilion.needs:
        if can_unload_color_at_pavilion(state, pavilion, color):
            eligible_colors.append(color)

    if not eligible_colors:
        # Check if there's carried stuff that can't be unloaded (for rejection logging)
        for (ft, c), qty in state.load.items():
            if ft == pavilion.type and c in pavilion.needs:
                rem = state.remaining_needs.get((pavilion.id, c), 0)
                if rem > 0 and qty < rem:
                    rejected.append(
                        RejectedRecord(
                            state.id,
                            f"Unload {ft} {c} at {pavilion.id}",
                            f"Carried {qty} < needed {rem} (partial unload forbidden).",
                        )
                    )
        return children, rejected

    # Generate unload actions:
    #   1. Unload ALL eligible colors at once (always best since cost=1)
    #   2. Unload each individual color separately (for flexibility)
    seen_sigs: set = set()

    def _build_unload(colors_to_unload):
        new_load = dict(state.load)
        new_needs = dict(state.remaining_needs)
        unload_desc_parts = []
        for c in colors_to_unload:
            rem = new_needs[(pavilion.id, c)]
            new_load[(pavilion.type, c)] -= rem
            if new_load[(pavilion.type, c)] == 0:
                del new_load[(pavilion.type, c)]
            del new_needs[(pavilion.id, c)]
            unload_desc_parts.append(f"{pavilion.type} {c} x{rem}")

        desc = (
            f"Unload at {pavilion.id} "
            f"[{', '.join(unload_desc_parts)}]"
        )
        child = _make_child(
            state, state.robot_pos, new_load, new_needs,
            "Unload", desc, problem, counter,
        )
        sig = child.signature()
        if sig not in seen_sigs:
            seen_sigs.add(sig)
            children.append(child)

    # Option 1: Unload ALL eligible colors at once
    _build_unload(eligible_colors)

    # Option 2: Each individual color separately (if >1 eligible)
    if len(eligible_colors) > 1:
        for single_color in eligible_colors:
            _build_unload([single_color])

    return children, rejected


# ═══════════════════════════════════════════════════════════════════════════════
#  Top-level successor generator
# ═══════════════════════════════════════════════════════════════════════════════

def generate_successors(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[List[State], List[RejectedRecord]]:
    """Generate *all* valid successor states (moves + loads + unloads).

    Returns (children, rejected).
    """
    all_children: List[State] = []
    all_rejected: List[RejectedRecord] = []

    # Movements
    ch, rj = generate_moves(state, problem, counter)
    all_children.extend(ch)
    all_rejected.extend(rj)

    # Loads (only at warehouse)
    ch, rj = generate_loads(state, problem, counter)
    all_children.extend(ch)
    all_rejected.extend(rj)

    # Unloads (only at a pavilion)
    ch, rj = generate_unloads(state, problem, counter)
    all_children.extend(ch)
    all_rejected.extend(rj)

    return all_children, all_rejected
