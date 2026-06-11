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


from core.actions import StateCounter
from core.models import Position, Pavilion, Action, Problem, RejectedRecord, State
from core.heuristics import heuristic as compute_heuristic
from expert.facts import (
    CurrentStateFact,
    GeneratedStateFact,
    GoalFact,
    GridFact,
    PavilionFact,
    RobotFact,
    ViolationFact,
    WarehouseFact,
    MoveCandidateFact,
    LoadCandidateFact,
    ValidLoadFact,
    UnloadCandidateFact,
    ValidUnloadFact,
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

    # ══════════════════════════════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════════════════════════════

    def _make_child(
        self,
        parent: State,
        robot_pos: Position,
        load: Dict[Tuple[str, str], int],
        remaining_needs: Dict[Tuple[str, str], int],
        action_name: str,
        action_desc: str,
        problem: Problem,
        counter: StateCounter,
    ) -> State:
        new_id = counter.next()
        g = parent.g + 1
        h = compute_heuristic(
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

    def _format_load_batch(self, batch: Dict[Tuple[str, str], int]) -> str:
        items = sorted(batch.items())
        return "[" + ", ".join(f"{ft} {c} x{q}" for (ft, c), q in items) + "]"

    def _positive_subset_sums(self, values: List[int]) -> List[int]:
        if not values:
            return []
        sums = set()
        import itertools
        for r in range(1, len(values) + 1):
            for subset in itertools.combinations(values, r):
                s = sum(subset)
                if s > 0:
                    sums.add(s)
        return sorted(list(sums))

    def _deduplicate_batches(self, batches: List[Dict[Tuple[str, str], int]]) -> List[Dict[Tuple[str, str], int]]:
        seen = set()
        unique = []
        for b in batches:
            sig = frozenset(b.items())
            if sig not in seen:
                seen.add(sig)
                unique.append(b)
        return unique

    def _find_pavilion_at(self, pos: Position, problem: Problem) -> Pavilion | None:
        for pav in problem.pavilions:
            if pav.position == pos:
                return pav
        return None

    def _generate_same_type_loads(self, state: State, problem: Problem) -> List[Dict[Tuple[str, str], int]]:
        results: List[Dict[Tuple[str, str], int]] = []
        current_total = state.load_total()
        capacity = problem.max_load - current_total
        if capacity <= 0:
            return results

        import itertools
        for flower_type in problem.flowers:
            color_to_needs: Dict[str, List[int]] = {}
            for pav in problem.pavilions:
                if pav.type == flower_type:
                    for color in pav.needs:
                        rem = state.remaining_needs.get((pav.id, color), 0)
                        if rem > 0:
                            color_to_needs.setdefault(color, []).append(rem)
                            
            if not color_to_needs:
                continue
                
            color_possible_quantities: Dict[str, List[int]] = {}
            for color, needs_list in color_to_needs.items():
                color_possible_quantities[color] = self._positive_subset_sums(needs_list)
                
            colors = list(color_possible_quantities.keys())
            
            for r in range(1, len(colors) + 1):
                for color_combo in itertools.combinations(colors, r):
                    quantities_lists = [color_possible_quantities[c] for c in color_combo]
                    for qty_combo in itertools.product(*quantities_lists):
                        total = sum(qty_combo)
                        if total > 0 and total <= capacity:
                            batch = {}
                            for c, q in zip(color_combo, qty_combo):
                                batch[(flower_type, c)] = q
                            results.append(batch)

        return self._deduplicate_batches(results)

    def _generate_same_color_loads(self, state: State, problem: Problem) -> List[Dict[Tuple[str, str], int]]:
        results: List[Dict[Tuple[str, str], int]] = []
        current_total = state.load_total()
        capacity = problem.max_load - current_total
        if capacity <= 0:
            return results

        all_colors = set()
        for pav in problem.pavilions:
            all_colors.update(pav.needs)
            
        import itertools
        for color in all_colors:
            type_to_needs: Dict[str, List[int]] = {}
            for pav in problem.pavilions:
                rem = state.remaining_needs.get((pav.id, color), 0)
                if rem > 0:
                    type_to_needs.setdefault(pav.type, []).append(rem)
                    
            if len(type_to_needs) < 2:
                continue
                
            type_possible_quantities: Dict[str, List[int]] = {}
            for ft, needs_list in type_to_needs.items():
                type_possible_quantities[ft] = self._positive_subset_sums(needs_list)
                
            types = list(type_possible_quantities.keys())
            
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

        return self._deduplicate_batches(results)

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

        # Declare Move candidates:
        self.declare(MoveCandidateFact(parent_id=state.id, direction="Move Right", new_x=state.robot_pos.x + 1, new_y=state.robot_pos.y))
        self.declare(MoveCandidateFact(parent_id=state.id, direction="Move Left", new_x=state.robot_pos.x - 1, new_y=state.robot_pos.y))
        self.declare(MoveCandidateFact(parent_id=state.id, direction="Move Up", new_x=state.robot_pos.x, new_y=state.robot_pos.y - 1))
        self.declare(MoveCandidateFact(parent_id=state.id, direction="Move Down", new_x=state.robot_pos.x, new_y=state.robot_pos.y + 1))

        # Declare Load candidates (only at warehouse):
        if state.robot_pos == problem.warehouse:
            batches_raw = self._generate_same_type_loads(state, problem)
            batches_raw.extend(self._generate_same_color_loads(state, problem))
            batches = self._deduplicate_batches(batches_raw)
            for batch in batches:
                self.declare(LoadCandidateFact(parent_id=state.id, batch=batch))

        # Declare Unload candidates (only at pavilion):
        pavilion = self._find_pavilion_at(state.robot_pos, problem)
        if pavilion is not None:
            eligible_colors = []
            for color in pavilion.needs:
                remaining = state.remaining_needs.get((pavilion.id, color), 0)
                if remaining > 0:
                    carried = state.load.get((pavilion.type, color), 0)
                    if carried >= remaining:
                        eligible_colors.append(color)

            if eligible_colors:
                self.declare(UnloadCandidateFact(parent_id=state.id, pavilion_id=pavilion.id, colors_to_unload=tuple(eligible_colors)))
                if len(eligible_colors) > 1:
                    for single_color in eligible_colors:
                        self.declare(UnloadCandidateFact(parent_id=state.id, pavilion_id=pavilion.id, colors_to_unload=(single_color,)))
            else:
                for (ft, c), qty in state.load.items():
                    if ft == pavilion.type and c in pavilion.needs:
                        rem = state.remaining_needs.get((pavilion.id, c), 0)
                        if rem > 0 and qty < rem:
                            action_desc = f"Unload {ft} {c} at {pavilion.id}"
                            self.declare(ViolationFact(
                                parent_id=state.id,
                                action=action_desc,
                                reason=f"Carried {qty} < needed {rem} (partial unload forbidden).",
                            ))

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
        MoveCandidateFact(parent_id=MATCH.sid, direction=MATCH.dir, new_x=MATCH.nx, new_y=MATCH.ny),
        GridFact(width=MATCH.w, height=MATCH.h),
        TEST(lambda nx, ny, w, h: 1 <= nx <= w and 1 <= ny <= h),
    )
    def move_valid_rule(self, sid, dir, nx, ny, w, h):
        new_pos = Position(nx, ny)
        action_desc = f"{dir} -> robot at {new_pos}"
        child = self._make_child(
            self.current_state,
            new_pos,
            dict(self.current_state.load),
            dict(self.current_state.remaining_needs),
            dir,
            action_desc,
            self.problem,
            self.counter,
        )
        self.generated_children.append(child)
        self.declare(GeneratedStateFact(state_id=child.id, action=action_desc))

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        MoveCandidateFact(parent_id=MATCH.sid, direction=MATCH.dir, new_x=MATCH.nx, new_y=MATCH.ny),
        GridFact(width=MATCH.w, height=MATCH.h),
        TEST(lambda nx, ny, w, h: not (1 <= nx <= w and 1 <= ny <= h)),
    )
    def move_invalid_rule(self, sid, dir, nx, ny, w, h):
        reason = f"Position ({nx},{ny}) is outside the grid."
        self.declare(ViolationFact(
            parent_id=sid,
            action=dir,
            reason=reason,
        ))

    # ══════════════════════════════════════════════════════════════════
    #  LOAD RULES
    # ══════════════════════════════════════════════════════════════════

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        LoadCandidateFact(parent_id=MATCH.sid, batch=MATCH.batch),
    )
    def validate_load_candidate(self, sid, batch):
        reasons = []
        for qty in batch.values():
            if qty <= 0:
                reasons.append("Load quantities must be positive.")
                break
        
        current_total = self.current_state.load_total()
        batch_total = sum(batch.values())
        if (current_total + batch_total) > self.problem.max_load:
            reasons.append("Load would exceed max_load capacity.")
            
        combined = dict(self.current_state.load)
        for k, v in batch.items():
            combined[k] = combined.get(k, 0) + v
            
        if len(combined) > 1:
            types = set(ft for ft, _ in combined.keys())
            colors = set(c for _, c in combined.keys())
            if not (len(colors) == 1 or len(types) == 1):
                reasons.append("Total robot load violates pattern constraint (must be same-color or same-type).")
                
        for (ft, color), qty in batch.items():
            found = False
            for pav in self.problem.pavilions:
                if pav.type == ft:
                    rem = self.current_state.remaining_needs.get((pav.id, color), 0)
                    if rem > 0:
                        found = True
                        break
            if not found:
                reasons.append("Load contains bouquets not needed by any pavilion.")
                break
                
        action_desc = f"Load {self._format_load_batch(batch)}"
        if reasons:
            self.declare(ViolationFact(parent_id=sid, action=action_desc, reason=reasons[0]))
        else:
            self.declare(ValidLoadFact(parent_id=sid, batch=batch))

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        ValidLoadFact(parent_id=MATCH.sid, batch=MATCH.batch),
    )
    def execute_valid_load(self, sid, batch):
        action_desc = f"Load {self._format_load_batch(batch)}"
        new_load = dict(self.current_state.load)
        for key, qty in batch.items():
            new_load[key] = new_load.get(key, 0) + qty
        child = self._make_child(
            self.current_state,
            self.current_state.robot_pos,
            new_load,
            dict(self.current_state.remaining_needs),
            "Load",
            action_desc,
            self.problem,
            self.counter,
        )
        self.generated_children.append(child)
        self.declare(GeneratedStateFact(state_id=child.id, action=action_desc))

    # ══════════════════════════════════════════════════════════════════
    #  UNLOAD RULES
    # ══════════════════════════════════════════════════════════════════

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        UnloadCandidateFact(parent_id=MATCH.sid, pavilion_id=MATCH.pid, colors_to_unload=MATCH.colors),
    )
    def validate_unload_candidate(self, sid, pid, colors):
        self.declare(ValidUnloadFact(parent_id=sid, pavilion_id=pid, colors_to_unload=colors))

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        ValidUnloadFact(parent_id=MATCH.sid, pavilion_id=MATCH.pid, colors_to_unload=MATCH.colors),
    )
    def execute_valid_unload(self, sid, pid, colors):
        pavilion = next(p for p in self.problem.pavilions if p.id == pid)
        new_load = dict(self.current_state.load)
        new_needs = dict(self.current_state.remaining_needs)
        unload_desc_parts = []
        for c in colors:
            rem = new_needs[(pid, c)]
            new_load[(pavilion.type, c)] -= rem
            if new_load[(pavilion.type, c)] == 0:
                del new_load[(pavilion.type, c)]
            del new_needs[(pid, c)]
            unload_desc_parts.append(f"{pavilion.type} {c} x{rem}")

        action_desc = f"Unload at {pid} [{', '.join(unload_desc_parts)}]"
        child = self._make_child(
            self.current_state,
            self.current_state.robot_pos,
            new_load,
            new_needs,
            "Unload",
            action_desc,
            self.problem,
            self.counter,
        )
        self.generated_children.append(child)
        self.declare(GeneratedStateFact(state_id=child.id, action=action_desc))

    # ══════════════════════════════════════════════════════════════════
    #  GOAL DETECTION RULE
    # ══════════════════════════════════════════════════════════════════

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        RobotFact(has_load=False),
    )
    def detect_goal_rule(self, sid):
        all_satisfied = True
        for qty in self.current_state.remaining_needs.values():
            if qty > 0:
                all_satisfied = False
                break
        if all_satisfied:
            self.goal_reached = True
            self.declare(GoalFact(state_id=sid))

    # ══════════════════════════════════════════════════════════════════
    #  VIOLATION & LOGGING RULES
    # ══════════════════════════════════════════════════════════════════

    @Rule(
        CurrentStateFact(state_id=MATCH.sid),
        ViolationFact(parent_id=MATCH.sid, action=MATCH.act, reason=MATCH.reason),
    )
    def handle_violation(self, sid, act, reason):
        rej = RejectedRecord(sid, act, reason)
        if rej not in self.rejected_actions:
            self.rejected_actions.append(rej)

    @Rule(GeneratedStateFact(state_id=MATCH.sid, action=MATCH.act))
    def print_generated_state_rule(self, sid, act):
        self.log_lines.append(f"  [Generated] State {sid} via {act}")

    @Rule(ViolationFact(parent_id=MATCH.pid, action=MATCH.act, reason=MATCH.reason))
    def print_violation_rule(self, pid, act, reason):
        self.log_lines.append(f"  [Violation] Parent {pid} | {act} | {reason}")

    @Rule(GoalFact(state_id=MATCH.sid))
    def print_goal_rule(self, sid):
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
