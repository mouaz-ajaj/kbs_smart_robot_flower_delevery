"""
core/actions.py
===============
[DEPRECATED] This module is kept only for backward compatibility.
The authoritative action generation and validation logic now lives completely
in `expert/engine.py`. This file will be deleted in a later phase.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from core.heuristics import heuristic
from core.models import Action, Pavilion, Position, Problem, RejectedRecord, State


from core.state_utils import StateCounter


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
    """[DEPRECATED/WRAPPER] Generate Move Right using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)
    child = next((c for c in children if c.action.startswith("Move Right")), None)
    rej = next((r for r in rejected if r.action == "Move Right"), None)
    return child, rej


def generate_move_left(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[State | None, RejectedRecord | None]:
    """[DEPRECATED/WRAPPER] Generate Move Left using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)
    child = next((c for c in children if c.action.startswith("Move Left")), None)
    rej = next((r for r in rejected if r.action == "Move Left"), None)
    return child, rej


def generate_move_up(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[State | None, RejectedRecord | None]:
    """[DEPRECATED/WRAPPER] Generate Move Up using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)
    child = next((c for c in children if c.action.startswith("Move Up")), None)
    rej = next((r for r in rejected if r.action == "Move Up"), None)
    return child, rej


def generate_move_down(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[State | None, RejectedRecord | None]:
    """[DEPRECATED/WRAPPER] Generate Move Down using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)
    child = next((c for c in children if c.action.startswith("Move Down")), None)
    rej = next((r for r in rejected if r.action == "Move Down"), None)
    return child, rej


def generate_moves(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[List[State], List[RejectedRecord]]:
    """[DEPRECATED/WRAPPER] Generate all valid move actions using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)
    move_children = [c for c in children if c.action.startswith("Move")]
    move_rejected = [r for r in rejected if r.action.startswith("Move")]
    return move_children, move_rejected


def generate_same_type_loads(
    state: State, problem: Problem
) -> List[Dict[Tuple[str, str], int]]:
    """[DEPRECATED/WRAPPER] Generate candidate loads of same type using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    return FlowerRobotEngine()._generate_same_type_loads(state, problem)


def generate_same_color_loads(
    state: State, problem: Problem
) -> List[Dict[Tuple[str, str], int]]:
    """[DEPRECATED/WRAPPER] Generate candidate loads of same color using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    return FlowerRobotEngine()._generate_same_color_loads(state, problem)


def generate_loads(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[List[State], List[RejectedRecord]]:
    """[DEPRECATED/WRAPPER] Generate valid load actions using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)
    load_children = [c for c in children if c.action.startswith("Load")]
    load_rejected = [r for r in rejected if r.action.startswith("Load")]
    return load_children, load_rejected


def generate_unloads(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[List[State], List[RejectedRecord]]:
    """[DEPRECATED/WRAPPER] Generate valid unload actions using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)
    unload_children = [c for c in children if c.action.startswith("Unload")]
    unload_rejected = [r for r in rejected if r.action.startswith("Unload")]
    return unload_children, unload_rejected


def generate_successors(
    state: State, problem: Problem, counter: StateCounter
) -> Tuple[List[State], List[RejectedRecord]]:
    """[DEPRECATED/WRAPPER] Generate all valid successor states using FlowerRobotEngine."""
    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)
    return children, rejected

