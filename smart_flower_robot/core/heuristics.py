"""
core/heuristics.py
==================
Heuristic functions for A* search.

The heuristic h(n) must be **admissible** (never over-estimates the true
remaining cost) so that A* is guaranteed to find the optimal solution.

Components of the heuristic
----------------------------
1. Operations cost: 1 for each required load + 1 for each required unload.
2. Distance cost: lower bound on the Manhattan distance needed to complete
   all remaining deliveries, including return trips to the warehouse.
"""

from __future__ import annotations

import math
from typing import Dict, Tuple

from core.models import Position, Problem


# ===========================================================================
#  Manhattan distance
# ===========================================================================

def manhattan_distance(a: Position, b: Position) -> int:
    """Return the Manhattan (L1) distance between two positions."""
    return abs(a.x - b.x) + abs(a.y - b.y)


# ===========================================================================
#  Heuristic
# ===========================================================================
def heuristic(
    robot_pos: Position,
    load: Dict[Tuple[str, str], int],
    remaining_needs: Dict[Tuple[str, str], int],
    problem: Problem,
) -> float:
    """
    Fast heuristic for A*.

    Formula for empty-load states:
        h = d(robot, warehouse)
            + (trips - 1) * (2 * D_avg + 2)
            + D_avg
            + 2

    Meaning:
        d(robot, warehouse): cost to reach warehouse
        trips: estimated number of required delivery trips
        D_avg: average Manhattan distance from warehouse to needy pavilions
        +2: one load operation + one unload operation

    Note:
        This heuristic is designed for speed. It is not guaranteed to be
        strictly admissible in all cases.
    """
    total_remaining = sum(qty for qty in remaining_needs.values() if qty > 0)
    current_load = sum(load.values())

    if total_remaining == 0 and current_load == 0:
        return 0.0

    needy_pavilion_ids = {
        pid
        for (pid, _color), qty in remaining_needs.items()
        if qty > 0
    }

    if not needy_pavilion_ids:
        return 0.0

    needy_pavilions = [
        pav for pav in problem.pavilions
        if pav.id in needy_pavilion_ids
    ]

    distances = [
        manhattan_distance(problem.warehouse, pav.position)
        for pav in needy_pavilions
    ]

    if not distances:
        return 0.0

    d_avg = sum(distances) / len(distances)

    # If robot is empty, it must go to warehouse first.
    if current_load == 0:
        trips = math.ceil(total_remaining / problem.max_load)

        if trips <= 0:
            return 0.0

        return (
            manhattan_distance(robot_pos, problem.warehouse)
            + max(0, trips - 1) * (2 * d_avg + 2)
            + d_avg
            + 2
        )

    # If robot already carries bouquets, do not force it to go back
    # to warehouse first. Estimate delivery of current load first.
    min_deliver_dist = float("inf")

    for pav in needy_pavilions:
        for (flower_type, color), qty in load.items():
            if flower_type != pav.type:
                continue

            remaining = remaining_needs.get((pav.id, color), 0)

            if remaining > 0 and qty >= remaining:
                dist = manhattan_distance(robot_pos, pav.position)
                min_deliver_dist = min(min_deliver_dist, dist)

    if min_deliver_dist == float("inf"):
        min_deliver_dist = min(
            manhattan_distance(robot_pos, pav.position)
            for pav in needy_pavilions
        )

    remaining_to_load = max(0, total_remaining - current_load)
    trips = math.ceil(remaining_to_load / problem.max_load)

    return (
        min_deliver_dist
        + 1
        + trips * (2 * d_avg + 2)
    )