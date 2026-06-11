"""
core/parser.py
==============
Reads and validates the JSON problem file, then converts it into a Problem
object (and the initial State).

Responsibilities:
    1. Read JSON from disk.
    2. Verify all required fields exist and have the correct types.
    3. Validate that every pavilion's color needs match the flower definition.
    4. Compute max_load automatically (largest single-pavilion total need).
    5. Build the initial State (robot at start, empty load, full remaining needs).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from core.models import Action, Pavilion, Position, Problem, State


# ── Required top-level keys ──────────────────────────────────────────────────
_REQUIRED_KEYS = {"grid", "warehouse", "robot", "flowers", "pavilions"}


# ═══════════════════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════════════════

def load_json(filepath: str | Path) -> dict:
    """Read a JSON file and return the raw dict.

    Raises:
        FileNotFoundError : if the file does not exist
        json.JSONDecodeError : if the file is not valid JSON
    """
    filepath = Path(filepath)
    if not filepath.exists():
        raise FileNotFoundError(f"JSON file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as fh:
        return json.load(fh)


def parse_problem(data: dict) -> Problem:
    """Convert a raw JSON dict into a validated Problem object.

    Raises:
        ValueError : for missing / invalid fields or inconsistent data
    """
    _validate_top_level(data)

    # ── Grid ──────────────────────────────────────────────────────────
    grid = data["grid"]
    _require_keys(grid, {"width", "height"}, context="grid")
    grid_w = int(grid["width"])
    grid_h = int(grid["height"])
    if grid_w < 1 or grid_h < 1:
        raise ValueError(f"Grid dimensions must be ≥ 1, got {grid_w}x{grid_h}")

    # ── Warehouse ─────────────────────────────────────────────────────
    wh = data["warehouse"]
    _require_keys(wh, {"x", "y"}, context="warehouse")
    warehouse = Position(int(wh["x"]), int(wh["y"]))
    _check_bounds(warehouse, grid_w, grid_h, "warehouse")

    # ── Robot ─────────────────────────────────────────────────────────
    rb = data["robot"]
    _require_keys(rb, {"x", "y"}, context="robot")
    robot_start = Position(int(rb["x"]), int(rb["y"]))
    _check_bounds(robot_start, grid_w, grid_h, "robot")

    # ── Flowers ───────────────────────────────────────────────────────
    flowers: Dict[str, List[str]] = {}
    for ftype, colors in data["flowers"].items():
        if not isinstance(colors, list) or len(colors) == 0:
            raise ValueError(
                f"Flower type '{ftype}' must have a non-empty list of colors."
            )
        flowers[ftype] = list(colors)

    # ── Pavilions ─────────────────────────────────────────────────────
    pavilions: List[Pavilion] = []
    seen_ids: set = set()
    for idx, pav_raw in enumerate(data["pavilions"]):
        _require_keys(
            pav_raw, {"id", "type", "x", "y", "needs"},
            context=f"pavilion #{idx}",
        )
        pid = str(pav_raw["id"])
        if pid in seen_ids:
            raise ValueError(f"Duplicate pavilion id: {pid}")
        seen_ids.add(pid)

        ptype = str(pav_raw["type"])
        if ptype not in flowers:
            raise ValueError(
                f"Pavilion {pid}: flower type '{ptype}' is not defined in flowers."
            )

        pos = Position(int(pav_raw["x"]), int(pav_raw["y"]))
        _check_bounds(pos, grid_w, grid_h, f"pavilion {pid}")

        needs: Dict[str, int] = {}
        for color, qty in pav_raw["needs"].items():
            qty = int(qty)
            if qty <= 0:
                raise ValueError(
                    f"Pavilion {pid}: need quantity for '{color}' must be > 0."
                )
            if color not in flowers[ptype]:
                raise ValueError(
                    f"Pavilion {pid}: color '{color}' is not valid for "
                    f"flower type '{ptype}'.  Valid colors: {flowers[ptype]}"
                )
            needs[color] = qty

        pavilions.append(Pavilion(id=pid, type=ptype, position=pos, needs=needs))

    if len(pavilions) == 0:
        raise ValueError("At least one pavilion must be defined.")

    # ── max_load = largest single-pavilion total need ────────────────
    max_load = max(sum(p.needs.values()) for p in pavilions)

    return Problem(
        grid_width=grid_w,
        grid_height=grid_h,
        warehouse=warehouse,
        robot_start=robot_start,
        flowers=flowers,
        pavilions=pavilions,
        max_load=max_load,
    )


def build_initial_state(problem: Problem) -> State:
    """Create the initial search state from a parsed Problem."""
    remaining: Dict[Tuple[str, str], int] = {}
    for pav in problem.pavilions:
        for color, qty in pav.needs.items():
            remaining[(pav.id, color)] = qty

    return State(
        id=0,
        robot_pos=problem.robot_start,
        load={},
        remaining_needs=remaining,
        g=0,
        h=0.0,
        f=0.0,
        path=[],
        parent_id=-1,
        action="Initial State",
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _validate_top_level(data: dict) -> None:
    missing = _REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"Missing top-level keys in JSON: {missing}")


def _require_keys(obj: dict, keys: set, *, context: str) -> None:
    missing = keys - set(obj.keys())
    if missing:
        raise ValueError(f"Missing keys in {context}: {missing}")


def _check_bounds(pos: Position, w: int, h: int, label: str) -> None:
    if pos.x < 1 or pos.x > w or pos.y < 1 or pos.y > h:
        raise ValueError(
            f"{label} position {pos} is outside the grid (1..{w}, 1..{h})."
        )
