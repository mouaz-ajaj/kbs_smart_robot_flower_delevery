"""
core/search.py
==============
Search algorithms for the Smart Flower Robot problem.

Provides:
    1. **A* Search** – finds the optimal solution using f(n) = g(n) + h(n).
    2. **Search-tree generation** – limited-depth BFS expansion for
       visualising the state space.
    3. **Tree formatting** – pretty-prints the search tree in a textual
       hierarchical format.
"""

from __future__ import annotations

import heapq
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from core.actions import StateCounter, generate_successors
from core.heuristics import heuristic
from core.models import Problem, RejectedRecord, State
from core.validators import is_goal_state, state_signature


# ═══════════════════════════════════════════════════════════════════════════════
#  A* Search
# ═══════════════════════════════════════════════════════════════════════════════

class AStarResult:
    """Container for A* search results."""

    def __init__(self):
        self.solution: Optional[State] = None
        self.all_states: List[State] = []
        self.rejected: List[RejectedRecord] = []
        self.visited_count: int = 0
        self.generated_count: int = 0
        self.iterations: int = 0
        self.success: bool = False


def a_star_search(
    initial_state: State,
    problem: Problem,
    max_iterations: int = 200_000,
) -> AStarResult:
    """Run A* search starting from *initial_state*.

    Parameters:
        initial_state  : the starting state (id=0, g=0)
        problem        : problem specification
        max_iterations : safety limit to prevent infinite loops

    Returns:
        AStarResult with solution path, all states, and rejected states.
    """
    result = AStarResult()
    counter = StateCounter(start=1)

    # Compute heuristic for the initial state
    initial_state.h = heuristic(
        initial_state.robot_pos,
        initial_state.load,
        initial_state.remaining_needs,
        problem,
    )
    initial_state.f = initial_state.g + initial_state.h

    # Open list: min-heap of (f, state_id, State)
    open_list: list = []
    heapq.heappush(open_list, (initial_state.f, initial_state.id, initial_state))

    # Closed set: signatures of already-expanded states
    visited: Set[tuple] = set()

    result.all_states.append(initial_state)

    while open_list and result.iterations < max_iterations:
        result.iterations += 1

        _f, _sid, current = heapq.heappop(open_list)

        sig = state_signature(current)
        if sig in visited:
            continue
        visited.add(sig)
        result.visited_count += 1

        # ── Goal test ─────────────────────────────────────────────────
        if is_goal_state(current):
            result.solution = current
            result.success = True
            return result

        # ── Expand ────────────────────────────────────────────────────
        children, rejected = generate_successors(current, problem, counter)
        result.rejected.extend(rejected)

        for child in children:
            child_sig = state_signature(child)
            if child_sig not in visited:
                heapq.heappush(open_list, (child.f, child.id, child))
                result.all_states.append(child)
                result.generated_count += 1

    # If we exit the loop without finding a solution
    return result


def dfs_search(
    initial_state: State,
    problem: Problem,
    max_iterations: int = 200_000,
    max_depth: int | None = None,
) -> AStarResult:
    """Procedural DFS kept for comparison/debugging.
    The final UI and CLI use expert.engine.engine_dfs_search.
    """
    result = AStarResult()
    counter = StateCounter(start=1)

    initial_state.h = heuristic(
        initial_state.robot_pos,
        initial_state.load,
        initial_state.remaining_needs,
        problem,
    )
    initial_state.f = initial_state.g + initial_state.h

    stack = [(initial_state, 0)]
    visited: Set[tuple] = set()

    result.all_states.append(initial_state)

    while stack and result.iterations < max_iterations:
        result.iterations += 1

        current, depth = stack.pop()

        sig = state_signature(current)
        if sig in visited:
            continue
        visited.add(sig)
        result.visited_count += 1

        if is_goal_state(current):
            result.solution = current
            result.success = True
            return result

        if max_depth is not None and depth >= max_depth:
            continue

        children, rejected = generate_successors(current, problem, counter)
        result.rejected.extend(rejected)

        for child in reversed(children):
            child_sig = state_signature(child)
            if child_sig not in visited:
                stack.append((child, depth + 1))
                result.all_states.append(child)
                result.generated_count += 1

    return result

# ═══════════════════════════════════════════════════════════════════════════════
#  Search-tree generation  (limited-depth BFS for visualisation)
# ═══════════════════════════════════════════════════════════════════════════════

class SearchTree:
    """A lightweight representation of a (partial) search tree."""

    def __init__(self):
        self.states: Dict[int, State] = {}          # id -> State
        self.children: Dict[int, List[int]] = {}     # parent_id -> [child_ids]
        self.rejected: List[RejectedRecord] = []
        self.root_id: int = 0


def generate_search_tree(
    initial_state: State,
    problem: Problem,
    max_depth: int = 3,
    max_states: int = 300,
) -> SearchTree:
    """Expand the state space using BFS up to *max_depth* levels.

    This is NOT for finding the optimal solution – it is for
    **visualising** the first few levels of the search tree.
    """
    counter = StateCounter(start=1)

    # Compute h for initial state
    initial_state.h = heuristic(
        initial_state.robot_pos,
        initial_state.load,
        initial_state.remaining_needs,
        problem,
    )
    initial_state.f = initial_state.g + initial_state.h

    tree = SearchTree()
    tree.root_id = initial_state.id
    tree.states[initial_state.id] = initial_state
    
    seen = {state_signature(initial_state)}

    # BFS queue: (state, depth)
    queue: deque = deque()
    queue.append((initial_state, 0))

    while queue and len(tree.states) < max_states:
        current, depth = queue.popleft()
        if depth >= max_depth:
            continue

        children, rejected = generate_successors(current, problem, counter)
        tree.rejected.extend(rejected)
        tree.children[current.id] = []

        for child in children:
            if len(tree.states) >= max_states:
                break
            child_sig = state_signature(child)
            if child_sig in seen:
                continue
            seen.add(child_sig)
            tree.states[child.id] = child
            tree.children[current.id].append(child.id)
            queue.append((child, depth + 1))

    return tree


# ═══════════════════════════════════════════════════════════════════════════════
#  Pretty-print helpers
# ═══════════════════════════════════════════════════════════════════════════════

def format_state_line(state: State) -> str:
    """One-line summary of a state."""
    return (
        f"State {state.id}: "
        f"robot={state.robot_pos}, "
        f"load={state.format_load()}, "
        f"g={state.g}, h={state.h:.1f}, f={state.f:.1f}"
    )


def format_search_tree(tree: SearchTree) -> str:
    """Render the search tree as an indented text string."""
    lines: List[str] = []
    _render_subtree(tree, tree.root_id, "", True, lines)
    return "\n".join(lines)


def _render_subtree(
    tree: SearchTree,
    node_id: int,
    prefix: str,
    is_last: bool,
    lines: List[str],
) -> None:
    """Recursive tree renderer with box-drawing connectors."""
    state = tree.states[node_id]

    # Connector
    if node_id == tree.root_id:
        connector = ""
        child_prefix = ""
    else:
        connector = "+-- " if is_last else "|-- "
        child_prefix = prefix + ("    " if is_last else "|   ")

    action_part = ""
    if state.action and state.action != "Initial State":
        action_part = f" via {state.action}"

    lines.append(
        f"{prefix}{connector}"
        f"State {state.id}{action_part}\n"
        f"{child_prefix}  robot={state.robot_pos}, "
        f"load={state.format_load()}, "
        f"g={state.g}, h={state.h:.1f}, f={state.f:.1f}"
    )

    child_ids = tree.children.get(node_id, [])
    for i, cid in enumerate(child_ids):
        is_last_child = (i == len(child_ids) - 1)
        _render_subtree(tree, cid, child_prefix, is_last_child, lines)


def format_solution(solution: State) -> str:
    """Format the solution path as a numbered step list."""
    lines: List[str] = ["Goal reached!", ""]
    lines.append(f"Total cost: {solution.g}")
    lines.append("")
    lines.append("Solution path:")
    lines.append("")
    for i, action in enumerate(solution.path, 1):
        lines.append(f"  {i}. {action.description}")
    return "\n".join(lines)


def format_rejected(rejected: List[RejectedRecord]) -> str:
    """Format rejected states / actions."""
    if not rejected:
        return "No rejected actions recorded."
    lines = ["Rejected Actions:", ""]
    for rec in rejected:
        lines.append(
            f"  Parent State {rec.parent_id} | "
            f"Action: {rec.action} | "
            f"Reason: {rec.reason}"
        )
    return "\n".join(lines)
