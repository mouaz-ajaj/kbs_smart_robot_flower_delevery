"""
expert/engine.py
================
Experta KnowledgeEngine for the Smart Flower Robot.

The engine contains Rules that represent all *knowledge-based decisions*:
    - Movement rules (right, left, up, down)
    - Loading rule (at warehouse)
    - Unloading rule (at pavilion)
    - Goal detection rule
    - Violation rules (overload, invalid pattern, invalid unload, outside grid)
    - Logging rules (print generated state, print search tree node)

Design philosophy
-----------------
Rules do NOT contain raw procedural logic.  Instead, each Rule:
    1. Pattern-matches on Facts (RobotFact, GridFact, WarehouseFact, etc.)
       to decide *when* it should fire.
    2. Delegates to clean functions in ``core/actions.py`` and
       ``core/validators.py`` for the *actual work*.
    3. Asserts new Facts (GeneratedStateFact, ViolationFact, GoalFact)
       to communicate results back to the engine.

This keeps the knowledge representation declarative while keeping the
implementation readable and maintainable.
"""

from __future__ import annotations

from typing import List
import collections
import collections.abc

# Monkey-patch collections.Mapping for frozendict/experta on Python 3.10+
if not hasattr(collections, "Mapping"):
    collections.Mapping = collections.abc.Mapping

from experta import MATCH, TEST, KnowledgeEngine, Rule

from core.actions import (
    StateCounter,
    generate_loads,
    generate_move_down,
    generate_move_left,
    generate_move_right,
    generate_move_up,
    generate_unloads,
)
from core.models import Problem, RejectedRecord, State
from core.validators import is_goal_state
from expert.facts import (
    CurrentStateFact,
    GeneratedStateFact,
    GoalFact,
    GridFact,
    PavilionFact,
    RobotFact,
    ViolationFact,
    WarehouseFact,
)


class FlowerRobotEngine(KnowledgeEngine):
    """Rule-based engine for expanding a single state.

    Usage::

        engine = FlowerRobotEngine()
        children, rejected, goal = engine.expand_state(state, problem, counter)

    The ``expand_state`` method:
        1. Resets the engine.
        2. Stores the current state and problem as instance attributes.
        3. Declares all relevant Facts.
        4. Runs the engine (fires all matching Rules).
        5. Returns the generated children, rejected actions, and goal flag.
    """

    def __init__(self):
        super().__init__()
        self.problem: Problem | None = None
        self.current_state: State | None = None
        self.counter: StateCounter | None = None
        self.generated_children: List[State] = []
        self.rejected_actions: List[RejectedRecord] = []
        self.goal_reached: bool = False
        self.log_lines: List[str] = []

    # ──────────────────────────────────────────────────────────────────
    #  Public API
    # ──────────────────────────────────────────────────────────────────

    def expand_state(
        self,
        state: State,
        problem: Problem,
        counter: StateCounter,
    ) -> tuple:
        """Expand *state* by firing all matching rules.

        Returns:
            (generated_children, rejected_actions, goal_reached)
        """
        self.problem = problem
        self.current_state = state
        self.counter = counter
        self.generated_children = []
        self.rejected_actions = []
        self.goal_reached = False
        self.log_lines = []

        self.reset()

        # Declare problem facts
        self.declare(GridFact(width=problem.grid_width, height=problem.grid_height))
        self.declare(WarehouseFact(x=problem.warehouse.x, y=problem.warehouse.y))
        self.declare(RobotFact(
            x=state.robot_pos.x,
            y=state.robot_pos.y,
            has_load=(state.load_total() > 0),
        ))
        for pav in problem.pavilions:
            self.declare(PavilionFact(
                pid=pav.id,
                flower_type=pav.type,
                x=pav.position.x,
                y=pav.position.y,
            ))
        self.declare(CurrentStateFact(state_id=state.id))

        self.run()

        return (
            list(self.generated_children),
            list(self.rejected_actions),
            self.goal_reached,
        )

    # ══════════════════════════════════════════════════════════════════
    #  MOVEMENT RULES
    # ══════════════════════════════════════════════════════════════════

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.rx, y=MATCH.ry),
        GridFact(width=MATCH.w),
        TEST(lambda rx, w: rx < w),
    )
    def move_right_rule(self, sid, rx, ry, w):
        """RULE: Move Right – robot x < grid width."""
        child, rej = generate_move_right(
            self.current_state, self.problem, self.counter
        )
        if child:
            self.generated_children.append(child)
            self.declare(GeneratedStateFact(state_id=child.id, action="Move Right"))
        if rej:
            self.rejected_actions.append(rej)

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.rx, y=MATCH.ry),
        GridFact(width=MATCH.w),
        TEST(lambda rx, w: rx >= w),
    )
    def violation_outside_grid_right(self, sid, rx, ry, w):
        """RULE: Violation – Move Right would exit the grid."""
        rej = RejectedRecord(sid, "Move Right", f"Robot at x={rx}, grid width={w}. Would exit grid.")
        self.rejected_actions.append(rej)
        self.declare(ViolationFact(
            parent_id=sid,
            action="Move Right",
            reason=f"Position ({rx+1},{ry}) is outside the grid.",
        ))

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.rx, y=MATCH.ry),
        TEST(lambda rx: rx > 1),
    )
    def move_left_rule(self, sid, rx, ry):
        """RULE: Move Left – robot x > 1."""
        child, rej = generate_move_left(
            self.current_state, self.problem, self.counter
        )
        if child:
            self.generated_children.append(child)
            self.declare(GeneratedStateFact(state_id=child.id, action="Move Left"))
        if rej:
            self.rejected_actions.append(rej)

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.rx, y=MATCH.ry),
        TEST(lambda rx: rx <= 1),
    )
    def violation_outside_grid_left(self, sid, rx, ry):
        """RULE: Violation – Move Left would exit the grid."""
        rej = RejectedRecord(sid, "Move Left", f"Robot at x={rx}. Would exit grid.")
        self.rejected_actions.append(rej)
        self.declare(ViolationFact(
            parent_id=sid,
            action="Move Left",
            reason=f"Position ({rx-1},{ry}) is outside the grid.",
        ))

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.rx, y=MATCH.ry),
        TEST(lambda ry: ry > 1),
    )
    def move_up_rule(self, sid, rx, ry):
        """RULE: Move Up – robot y > 1."""
        child, rej = generate_move_up(
            self.current_state, self.problem, self.counter
        )
        if child:
            self.generated_children.append(child)
            self.declare(GeneratedStateFact(state_id=child.id, action="Move Up"))
        if rej:
            self.rejected_actions.append(rej)

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.rx, y=MATCH.ry),
        TEST(lambda ry: ry <= 1),
    )
    def violation_outside_grid_up(self, sid, rx, ry):
        """RULE: Violation – Move Up would exit the grid."""
        rej = RejectedRecord(sid, "Move Up", f"Robot at y={ry}. Would exit grid.")
        self.rejected_actions.append(rej)
        self.declare(ViolationFact(
            parent_id=sid,
            action="Move Up",
            reason=f"Position ({rx},{ry-1}) is outside the grid.",
        ))

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.rx, y=MATCH.ry),
        GridFact(height=MATCH.h),
        TEST(lambda ry, h: ry < h),
    )
    def move_down_rule(self, sid, rx, ry, h):
        """RULE: Move Down – robot y < grid height."""
        child, rej = generate_move_down(
            self.current_state, self.problem, self.counter
        )
        if child:
            self.generated_children.append(child)
            self.declare(GeneratedStateFact(state_id=child.id, action="Move Down"))
        if rej:
            self.rejected_actions.append(rej)

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.rx, y=MATCH.ry),
        GridFact(height=MATCH.h),
        TEST(lambda ry, h: ry >= h),
    )
    def violation_outside_grid_down(self, sid, rx, ry, h):
        """RULE: Violation – Move Down would exit the grid."""
        rej = RejectedRecord(sid, "Move Down", f"Robot at y={ry}, grid height={h}. Would exit grid.")
        self.rejected_actions.append(rej)
        self.declare(ViolationFact(
            parent_id=sid,
            action="Move Down",
            reason=f"Position ({rx},{ry+1}) is outside the grid.",
        ))

    # ══════════════════════════════════════════════════════════════════
    #  LOAD RULE
    # ══════════════════════════════════════════════════════════════════

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.pos_x, y=MATCH.pos_y),
        WarehouseFact(x=MATCH.pos_x, y=MATCH.pos_y),
    )
    def load_rule(self, sid, pos_x, pos_y):
        """RULE: Load – robot is at the warehouse.

        Uses MATCH variable joining (pos_x, pos_y appear in both
        RobotFact and WarehouseFact) to enforce the location constraint
        entirely through Experta pattern matching.

        Delegates the actual load-option generation to
        ``core.actions.generate_loads``, which enforces same-color /
        same-type constraints, max_load, and need-based filtering.
        """
        children, rejected = generate_loads(
            self.current_state, self.problem, self.counter
        )
        for child in children:
            self.generated_children.append(child)
            self.declare(GeneratedStateFact(state_id=child.id, action=child.action))
        for rej in rejected:
            self.rejected_actions.append(rej)
            self.declare(ViolationFact(
                parent_id=rej.parent_id,
                action=rej.action,
                reason=rej.reason,
            ))

    # ══════════════════════════════════════════════════════════════════
    #  UNLOAD RULE
    # ══════════════════════════════════════════════════════════════════

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(x=MATCH.pos_x, y=MATCH.pos_y, has_load=True),
        PavilionFact(pid=MATCH.pid, x=MATCH.pos_x, y=MATCH.pos_y),
    )
    def unload_rule(self, sid, pos_x, pos_y, pid):
        """RULE: Unload – robot is at a pavilion AND is carrying bouquets.

        Pattern matching ensures:
            - Robot has a non-empty load  (has_load=True)
            - Robot is at a pavilion  (pos_x/pos_y join)

        Delegates to ``core.actions.generate_unloads`` for constraint
        checking (type match, minimum quantity, no partial unload).
        """
        children, rejected = generate_unloads(
            self.current_state, self.problem, self.counter
        )
        for child in children:
            self.generated_children.append(child)
            self.declare(GeneratedStateFact(state_id=child.id, action=child.action))
        for rej in rejected:
            self.rejected_actions.append(rej)
            self.declare(ViolationFact(
                parent_id=rej.parent_id,
                action=rej.action,
                reason=rej.reason,
            ))

    # ══════════════════════════════════════════════════════════════════
    #  GOAL DETECTION RULE
    # ══════════════════════════════════════════════════════════════════

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(has_load=False),
    )
    def detect_goal_rule(self, sid):
        """RULE: Detect Goal – robot has no load.

        This rule fires when the robot is empty.  It then checks
        whether ALL pavilion needs are also satisfied (remaining == 0).
        If so, it asserts a GoalFact.
        """
        if is_goal_state(self.current_state):
            self.goal_reached = True
            self.declare(GoalFact(state_id=sid))

    # ══════════════════════════════════════════════════════════════════
    #  LOGGING RULES
    # ══════════════════════════════════════════════════════════════════

    @Rule(GeneratedStateFact(state_id=MATCH.sid, action=MATCH.act))
    def print_generated_state_rule(self, sid, act):
        """RULE: Log generated state – fires for every successor."""
        self.log_lines.append(f"  [Generated] State {sid} via {act}")

    @Rule(ViolationFact(parent_id=MATCH.pid, action=MATCH.act, reason=MATCH.reason))
    def print_violation_rule(self, pid, act, reason):
        """RULE: Log violation – fires for every rejected action."""
        self.log_lines.append(f"  [Violation] Parent {pid} | {act} | {reason}")

    @Rule(GoalFact(state_id=MATCH.sid))
    def print_goal_rule(self, sid):
        """RULE: Log goal – fires when the goal is detected."""
        self.log_lines.append(f"  [GOAL] State {sid} is the goal state!")


# ═══════════════════════════════════════════════════════════════════════════════
#  Engine-based A* search  (wraps core/search.py but uses the engine for
#  state expansion instead of calling generate_successors directly)
# ═══════════════════════════════════════════════════════════════════════════════

import heapq
from typing import Optional, Set

from core.heuristics import heuristic as compute_heuristic
from core.search import AStarResult
from core.validators import state_signature


def engine_a_star_search(
    initial_state: State,
    problem: Problem,
    max_iterations: int = 200_000,
    log: bool = False,
) -> AStarResult:
    """A* search that uses the Experta engine for state expansion.

    Identical interface to ``core.search.a_star_search`` but every
    expansion goes through ``FlowerRobotEngine.expand_state``.
    """
    engine = FlowerRobotEngine()
    counter = StateCounter(start=1)
    result = AStarResult()

    # Heuristic for initial state
    initial_state.h = compute_heuristic(
        initial_state.robot_pos,
        initial_state.load,
        initial_state.remaining_needs,
        problem,
    )
    initial_state.f = initial_state.g + initial_state.h

    open_list: list = []
    heapq.heappush(open_list, (initial_state.f, initial_state.id, initial_state))
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

        # Goal test
        if is_goal_state(current):
            result.solution = current
            result.success = True
            return result

        # Expand via engine
        children, rejected, _goal = engine.expand_state(current, problem, counter)

        if log:
            for line in engine.log_lines:
                print(line)

        result.rejected.extend(rejected)

        for child in children:
            child_sig = state_signature(child)
            if child_sig not in visited:
                heapq.heappush(open_list, (child.f, child.id, child))
                result.all_states.append(child)
                result.generated_count += 1

    return result


def engine_dfs_search(
    initial_state: State,
    problem: Problem,
    max_iterations: int = 200_000,
    max_depth: int | None = None,
    log: bool = False,
) -> AStarResult:
    """DFS search that uses the Experta engine for state expansion."""
    engine = FlowerRobotEngine()
    counter = StateCounter(start=1)
    result = AStarResult()

    initial_state.h = compute_heuristic(
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

        children, rejected, _goal = engine.expand_state(current, problem, counter)

        if log:
            for line in engine.log_lines:
                print(line)

        result.rejected.extend(rejected)

        for child in reversed(children):
            child_sig = state_signature(child)
            if child_sig not in visited:
                stack.append((child, depth + 1))
                result.all_states.append(child)
                result.generated_count += 1

    return result
