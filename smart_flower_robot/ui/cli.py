"""
ui/cli.py
=========
Command-line interface for the Smart Flower Robot.

Provides a simple text-based way to:
    - Load and validate a JSON problem file
    - Display the initial state
    - Run A* search (engine-based)
    - Print the solution path
    - Generate and print the search tree
    - Export results to output/ files
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.models import Problem, State
from core.parser import build_initial_state, load_json, parse_problem
from core.search import (
    format_rejected,
    format_search_tree,
    format_solution,
    format_state_line,
    generate_search_tree,
)
from expert.engine import engine_a_star_search, engine_dfs_search

# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _separator(title: str = "") -> str:
    if title:
        return f"\n{'=' * 60}\n  {title}\n{'=' * 60}"
    return "=" * 60


def _export(content: str, filepath: Path) -> None:
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    print(f"  -> Exported to {filepath}")


# ═══════════════════════════════════════════════════════════════════════════════
#  Main CLI
# ═══════════════════════════════════════════════════════════════════════════════

def run_cli(json_path: str | None = None) -> None:
    """Entry point for the CLI."""
    if json_path is None:
        json_path = str(PROJECT_ROOT / "data" / "initial_state.json")

    print(_separator("Smart Flower Robot - CLI"))
    print(f"\n  Loading: {json_path}\n")

    # ── Load & parse ──────────────────────────────────────────────────
    try:
        data = load_json(json_path)
        problem = parse_problem(data)
    except (FileNotFoundError, ValueError) as exc:
        print(f"  ERROR: {exc}")
        return

    initial = build_initial_state(problem)

    # ── Print initial state ───────────────────────────────────────────
    print(_separator("Initial State"))
    print(f"\n  Grid: {problem.grid_width} x {problem.grid_height}")
    print(f"  Warehouse: {problem.warehouse}")
    print(f"  Robot start: {problem.robot_start}")
    print(f"  Max load: {problem.max_load}")
    print(f"  Pavilions:")
    for pav in problem.pavilions:
        needs_str = ", ".join(f"{c} x{q}" for c, q in pav.needs.items())
        print(f"    {pav.id} ({pav.type}) at {pav.position} - needs: {needs_str}")
    print(f"\n  {format_state_line(initial)}")

    # ── Run A* ────────────────────────────────────────────────────────
    print(_separator("Running A* Search (engine-based)"))
    result = engine_a_star_search(initial, problem, max_iterations=200_000)

    print(f"\n  Iterations : {result.iterations}")
    print(f"  Visited    : {result.visited_count}")
    print(f"  Generated  : {result.generated_count}")
    print(f"  Rejected   : {len(result.rejected)}")

    if result.success and result.solution:
        print(_separator("Solution"))
        sol_text = format_solution(result.solution)
        print(f"\n{sol_text}")
    else:
        print("\n  No solution found within iteration limit.")
        sol_text = "No solution found."

    # ── Run DFS ────────────────────────────────────────────────────────
    print(_separator("Running DFS Search (engine-based)"))
    dfs_result = engine_dfs_search(initial, problem, max_iterations=200_000)

    print(f"\n  Iterations : {dfs_result.iterations}")
    print(f"  Visited    : {dfs_result.visited_count}")
    print(f"  Generated  : {dfs_result.generated_count}")
    print(f"  Rejected   : {len(dfs_result.rejected)}")

    dfs_sol_text = ""
    if dfs_result.success and dfs_result.solution:
        dfs_sol_text = format_solution(dfs_result.solution)
        print(f"\n  Success! Solution cost: {dfs_result.solution.g}")
    else:
        print("\n  Failure: No solution found within limits.")
        dfs_sol_text = "No solution found."

    # ── Search tree ───────────────────────────────────────────────────
    print(_separator("Generating Search Tree (depth=2)"))
    tree = generate_search_tree(initial, problem, max_depth=2, max_states=200)
    tree_text = format_search_tree(tree)
    print(f"\n{tree_text}")

    # ── Rejected ──────────────────────────────────────────────────────
    if result.rejected:
        print(_separator("Rejected Actions (first 30)"))
        rej_text = format_rejected(result.rejected[:30])
        print(f"\n{rej_text}")
    else:
        rej_text = ""

    # ── Export ─────────────────────────────────────────────────────────
    output_dir = PROJECT_ROOT / "output"
    print(_separator("Exporting"))

    full_sol = sol_text
    if rej_text:
        full_sol += "\n\n" + format_rejected(result.rejected)

    dfs_full_sol = dfs_sol_text
    if dfs_result.rejected:
        dfs_full_sol += "\n\n" + format_rejected(dfs_result.rejected)

    _export(full_sol, output_dir / "solution.txt")
    _export(tree_text, output_dir / "search_tree.txt")
    _export(dfs_full_sol, output_dir / "dfs_solution.txt")

    print(_separator())
    print("  Done.\n")


# ═══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else None
    run_cli(path)
