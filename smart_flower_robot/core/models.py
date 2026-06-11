"""
core/models.py
==============
Data models for the Smart Flower Robot problem.

Uses Python dataclasses to represent:
  - Position          : (x, y) on the grid
  - Pavilion          : a flower pavilion with location, type, and color needs
  - Problem           : full problem specification (grid, warehouse, robot, pavilions)
  - State             : a search state (robot position, load, remaining needs, costs)
  - Action            : a named action with a human-readable description
  - RejectedRecord    : a record of a rejected state / action with its reason
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Position:
    """Immutable (x, y) coordinate on the grid.  1-indexed."""
    x: int
    y: int

    def __str__(self) -> str:
        return f"({self.x},{self.y})"


# ---------------------------------------------------------------------------
# Pavilion
# ---------------------------------------------------------------------------
@dataclass
class Pavilion:
    """A flower pavilion on the grid.

    Attributes:
        id       : unique identifier, e.g. "P1"
        type     : flower type this pavilion displays, e.g. "Rose"
        position : location on the grid
        needs    : mapping  color -> quantity  of bouquets required
    """
    id: str
    type: str
    position: Position
    needs: Dict[str, int]


# ---------------------------------------------------------------------------
# Problem
# ---------------------------------------------------------------------------
@dataclass
class Problem:
    """Complete problem specification loaded from JSON.

    Attributes:
        grid_width   : number of columns
        grid_height  : number of rows
        warehouse    : warehouse position
        robot_start  : robot's starting position
        flowers      : mapping  flower_type -> [valid colors]
        pavilions    : list of Pavilion objects
        max_load     : maximum bouquets the robot can carry at once
    """
    grid_width: int
    grid_height: int
    warehouse: Position
    robot_start: Position
    flowers: Dict[str, List[str]]
    pavilions: List[Pavilion]
    max_load: int


# ---------------------------------------------------------------------------
# Action
# ---------------------------------------------------------------------------
@dataclass
class Action:
    """Describes a single action taken by the robot.

    Attributes:
        name        : short action name, e.g. "Move Right", "Load", "Unload"
        description : human-readable detail, e.g. "Move Right -> robot at (2,3)"
    """
    name: str
    description: str


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
@dataclass
class State:
    """A node in the state-space search tree.

    Attributes:
        id              : unique state identifier (auto-incremented)
        robot_pos       : current robot position
        load            : bouquets the robot is carrying
                          {(flower_type, color): quantity}
        remaining_needs : outstanding pavilion needs
                          {(pavilion_id, color): quantity}
        g               : actual cost from start to this state
        h               : heuristic estimate of remaining cost
        f               : total estimated cost  f = g + h
        path            : ordered list of Action objects from start to here
        parent_id       : id of the parent state  (-1 for the initial state)
        action          : description of the action that produced this state
    """
    id: int
    robot_pos: Position
    load: Dict[Tuple[str, str], int]
    remaining_needs: Dict[Tuple[str, str], int]
    g: int
    h: float
    f: float
    path: List[Action] = field(default_factory=list)
    parent_id: int = -1
    action: str = ""

    # ------------------------------------------------------------------
    # Comparison for heapq  (min-heap by f, then by id as tie-breaker)
    # ------------------------------------------------------------------
    def __lt__(self, other: "State") -> bool:
        if self.f != other.f:
            return self.f < other.f
        return self.id < other.id

    # ------------------------------------------------------------------
    # State signature – used to detect duplicate states
    # ------------------------------------------------------------------
    def signature(self) -> tuple:
        """Return a hashable, comparable signature of the *meaningful*
        parts of this state (position, load, remaining needs).
        Two states with the same signature are considered identical
        regardless of path or cost."""
        load_sig = frozenset(
            (k, v) for k, v in self.load.items() if v > 0
        )
        needs_sig = frozenset(
            (k, v) for k, v in self.remaining_needs.items() if v > 0
        )
        return (self.robot_pos, load_sig, needs_sig)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def load_total(self) -> int:
        """Total number of bouquets currently carried."""
        return sum(self.load.values())

    def format_load(self) -> str:
        """Pretty-print the current load."""
        if not self.load:
            return "{}"
        items = sorted(self.load.items())
        return "{" + ", ".join(
            f"{ft} {c} x{q}" for (ft, c), q in items
        ) + "}"

    def format_needs(self) -> str:
        """Pretty-print remaining needs."""
        if not self.remaining_needs:
            return "{}"
        items = sorted(self.remaining_needs.items())
        return "{" + ", ".join(
            f"{pid}/{c}: {q}" for (pid, c), q in items
        ) + "}"


# ---------------------------------------------------------------------------
# RejectedRecord
# ---------------------------------------------------------------------------
@dataclass
class RejectedRecord:
    """Tracks a rejected (invalid) action or state with the rejection reason.

    Attributes:
        parent_id  : id of the state that tried the action
        action     : description of the attempted action
        reason     : why it was rejected
    """
    parent_id: int
    action: str
    reason: str
