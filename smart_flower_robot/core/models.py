
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Position:
    x: int
    y: int
    def __str__(self) -> str:
        return f"({self.x},{self.y})"



@dataclass
class Pavilion:
    id: str
    type: str
    position: Position
    needs: Dict[str, int]


@dataclass
class Problem:
    grid_width: int
    grid_height: int
    warehouse: Position
    robot_start: Position
    flowers: Dict[str, List[str]]
    pavilions: List[Pavilion]
    max_load: int



@dataclass
class Action:
    name: str
    description: str


@dataclass
class State:
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

    def __lt__(self, other: "State") -> bool:
        if self.f != other.f:
            return self.f < other.f
        return self.id < other.id


    def signature(self) -> tuple:
        load_sig = frozenset(
            (k, v) for k, v in self.load.items() if v > 0
        )
        needs_sig = frozenset(
            (k, v) for k, v in self.remaining_needs.items() if v > 0
        )
        return (self.robot_pos, load_sig, needs_sig)

    def load_total(self) -> int:
        return sum(self.load.values())

    def format_load(self) -> str:
        if not self.load:
            return "{}"
        items = sorted(self.load.items())
        return "{" + ", ".join(
            f"{ft} {c} x{q}" for (ft, c), q in items
        ) + "}"

    def format_needs(self) -> str:
        if not self.remaining_needs:
            return "{}"
        items = sorted(self.remaining_needs.items())
        return "{" + ", ".join(
            f"{pid}/{c}: {q}" for (pid, c), q in items
        ) + "}"


@dataclass
class RejectedRecord:
    parent_id: int
    action: str
    reason: str
