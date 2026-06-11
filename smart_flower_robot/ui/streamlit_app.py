"""
ui/streamlit_app.py
====================
Streamlit-based browser UI for the Smart Flower Robot.

Features:
    1.  Upload a JSON file or use the default ``data/initial_state.json``.
    2.  Display the initial state (grid, warehouse, robot, pavilions).
    3.  Visual grid showing R (robot), W (warehouse), P1..Pn (pavilions).
    4.  **Run A* Search** button → optimal solution display.
    5.  **Generate Search Tree** button → tree visualisation.
    6.  Step-by-step solution replay with state details.
    7.  Total cost display.
    8.  **Manual Mode** with directional buttons + Load / Unload.
    9.  **Reset** button.
    10. Export solution & search tree to ``output/``.

Run with:  ``streamlit run ui/streamlit_app.py``
"""

from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import streamlit as st

# Ensure project root is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.state_utils import StateCounter, is_goal_state
from core.heuristics import heuristic
from core.models import Action, Position, Problem, State
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
#  Page config
# ═══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Smart Flower Robot 🌹🤖",
    page_icon="🌹",
    layout="wide",
)

# ═══════════════════════════════════════════════════════════════════════════════
#  Custom CSS
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<style>
    .grid-cell {
        border: 2px solid #444;
        border-radius: 8px;
        padding: 6px;
        text-align: center;
        font-weight: bold;
        font-size: 0.85rem;
        min-height: 56px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 2px;
    }
    .cell-robot { background: #2196F3; color: white; }
    .cell-warehouse { background: #FF9800; color: white; }
    .cell-pavilion { background: #4CAF50; color: white; }
    .cell-robot-warehouse { background: linear-gradient(135deg, #2196F3, #FF9800); color: white; }
    .cell-robot-pavilion { background: linear-gradient(135deg, #2196F3, #4CAF50); color: white; }
    .cell-empty { background: #f5f5f5; color: #aaa; }
    .metric-box {
        background: linear-gradient(135deg, #1a1a2e, #16213e);
        border-radius: 12px;
        padding: 16px;
        color: white;
        text-align: center;
        margin: 4px 0;
    }
    .metric-box h3 { margin: 0; font-size: 0.9rem; color: #a8b2d1; }
    .metric-box p { margin: 4px 0 0 0; font-size: 1.3rem; font-weight: 700; }
    .stButton>button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  Session-state initialisation
# ═══════════════════════════════════════════════════════════════════════════════

def _init_session():
    defaults = {
        "problem": None,
        "initial_state": None,
        "current_state": None,
        "solution_result": None,
        "search_tree": None,
        "dfs_result": None,
        "manual_log": [],
        "manual_counter": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()


# ═══════════════════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _load_problem(data: dict):
    problem = parse_problem(data)
    initial = build_initial_state(problem)
    initial.h = heuristic(initial.robot_pos, initial.load, initial.remaining_needs, problem)
    initial.f = initial.g + initial.h
    st.session_state.problem = problem
    st.session_state.initial_state = initial
    st.session_state.current_state = deepcopy(initial)
    st.session_state.solution_result = None
    st.session_state.search_tree = None
    st.session_state.dfs_result = None
    st.session_state.manual_log = []
    st.session_state.manual_counter = StateCounter(start=1)


def _draw_grid(problem: Problem, state: State):
    """Draw the grid with robot, warehouse, and pavilion markers."""
    pav_map = {}
    for pav in problem.pavilions:
        pav_map[(pav.position.x, pav.position.y)] = pav.id

    for y in range(1, problem.grid_height + 1):
        cols = st.columns(problem.grid_width)
        for x in range(1, problem.grid_width + 1):
            is_robot = (state.robot_pos.x == x and state.robot_pos.y == y)
            is_wh = (problem.warehouse.x == x and problem.warehouse.y == y)
            is_pav = (x, y) in pav_map

            label_parts = []
            css_class = "cell-empty"

            if is_robot and is_wh:
                label_parts = ["🤖 R", "📦 W"]
                css_class = "cell-robot-warehouse"
            elif is_robot and is_pav:
                label_parts = ["🤖 R", f"🌺 {pav_map[(x, y)]}"]
                css_class = "cell-robot-pavilion"
            elif is_robot:
                label_parts = ["🤖 R"]
                css_class = "cell-robot"
            elif is_wh:
                label_parts = ["📦 W"]
                css_class = "cell-warehouse"
            elif is_pav:
                label_parts = [f"🌺 {pav_map[(x, y)]}"]
                css_class = "cell-pavilion"
            else:
                label_parts = [f"{x},{y}"]

            label = "<br>".join(label_parts)
            with cols[x - 1]:
                st.markdown(
                    f'<div class="grid-cell {css_class}">{label}</div>',
                    unsafe_allow_html=True,
                )


def _state_info(state: State, problem: Problem):
    """Show state details as metrics."""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f'<div class="metric-box"><h3>Position</h3><p>{state.robot_pos}</p></div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="metric-box"><h3>Load</h3><p>{state.load_total()} / {problem.max_load}</p></div>',
            unsafe_allow_html=True,
        )
    with c3:
        rem = sum(v for v in state.remaining_needs.values() if v > 0)
        st.markdown(
            f'<div class="metric-box"><h3>Remaining</h3><p>{rem} bouquets</p></div>',
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            f'<div class="metric-box"><h3>Cost (g)</h3><p>{state.g}</p></div>',
            unsafe_allow_html=True,
        )

    if state.load:
        with st.expander("🎒 Current Load Details"):
            for (ft, c), q in sorted(state.load.items()):
                st.write(f"- **{ft}** {c} × {q}")

    with st.expander("📋 Remaining Needs"):
        any_remaining = False
        for pav in problem.pavilions:
            pav_needs = []
            for color in pav.needs:
                rem = state.remaining_needs.get((pav.id, color), 0)
                if rem > 0:
                    pav_needs.append(f"{color} × {rem}")
            if pav_needs:
                any_remaining = True
                st.write(f"**{pav.id}** ({pav.type}): {', '.join(pav_needs)}")
        if not any_remaining:
            st.success("All needs satisfied! ✅")


# ═══════════════════════════════════════════════════════════════════════════════
#  Manual-mode helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _manual_move(dx: int, dy: int, name: str):
    state = st.session_state.current_state
    problem = st.session_state.problem
    counter = st.session_state.manual_counter

    from expert.engine import FlowerRobotEngine
    engine = FlowerRobotEngine()
    children, rejected, _ = engine.expand_state(state, problem, counter)

    child = next((c for c in children if c.action.startswith(name)), None)
    if child is not None:
        st.session_state.current_state = child
        st.session_state.manual_log.append(f"✅ {child.action}")
    else:
        rej = next((r for r in rejected if r.action == name), None)
        reason = rej.reason if rej else "outside grid"
        st.session_state.manual_log.append(f"❌ {name}: {reason}")



# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN UI
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.title("🌹 Smart Flower Robot 🤖")
    st.caption("Knowledge-Based Expert System – A* Search on a Flower Exhibition Grid")

    # ── Sidebar ───────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configuration")

        uploaded = st.file_uploader("Upload JSON", type=["json"])
        use_default = st.button("Use Default (data/initial_state.json)")

        if uploaded:
            try:
                data = json.load(uploaded)
                _load_problem(data)
                st.success("Loaded from upload!")
            except Exception as e:
                st.error(f"Error: {e}")

        if use_default:
            try:
                data = load_json(PROJECT_ROOT / "data" / "initial_state.json")
                _load_problem(data)
                st.success("Loaded default!")
            except Exception as e:
                st.error(f"Error: {e}")

        st.divider()

        if st.session_state.problem:
            st.header("🔍 Actions")

            if st.button("▶️ Run A* Search", type="primary"):
                with st.spinner("Searching..."):
                    result = engine_a_star_search(
                        deepcopy(st.session_state.initial_state),
                        st.session_state.problem,
                        max_iterations=200_000,
                    )
                    st.session_state.solution_result = result
                if result.success:
                    st.success(f"Solution found! Cost: {result.solution.g}")
                else:
                    st.warning("No solution found within limit.")

            if st.button("🔎 Run DFS Search", type="primary"):
                with st.spinner("Running DFS..."):
                    result = engine_dfs_search(
                        deepcopy(st.session_state.initial_state),
                        st.session_state.problem,
                        max_iterations=200_000,
                        max_depth=None
                    )
                    st.session_state.dfs_result = result
                if result.success:
                    st.success(f"DFS Solution found! Cost: {result.solution.g}")
                else:
                    st.warning("No DFS solution found within limit.")

            if st.button("🌳 Generate Search Tree"):
                with st.spinner("Generating..."):
                    tree = generate_search_tree(
                        deepcopy(st.session_state.initial_state),
                        st.session_state.problem,
                        max_depth=2,
                        max_states=200,
                    )
                    st.session_state.search_tree = tree
                st.success(f"Tree generated: {len(tree.states)} states")

            st.divider()

            if st.button("🔄 Reset"):
                st.session_state.current_state = deepcopy(st.session_state.initial_state)
                st.session_state.manual_log = []
                st.session_state.manual_counter = StateCounter(start=1)
                st.session_state.solution_result = None
                st.session_state.search_tree = None
                st.session_state.dfs_result = None
                st.rerun()

            st.divider()
            st.header("📥 Export")
            if st.button("💾 Export Solution"):
                res = st.session_state.solution_result
                if res and res.success:
                    out = PROJECT_ROOT / "output" / "solution.txt"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    content = format_solution(res.solution)
                    content += "\n\n" + format_rejected(res.rejected)
                    out.write_text(content, encoding="utf-8")
                    st.success(f"Exported to {out}")
                else:
                    st.warning("No solution to export.")

            if st.button("💾 Export Search Tree"):
                tr = st.session_state.search_tree
                if tr:
                    out = PROJECT_ROOT / "output" / "search_tree.txt"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(format_search_tree(tr), encoding="utf-8")
                    st.success(f"Exported to {out}")
                else:
                    st.warning("No tree to export. Generate first.")

            if st.button("💾 Export DFS Solution"):
                res = st.session_state.dfs_result
                if res and res.success:
                    out = PROJECT_ROOT / "output" / "dfs_solution.txt"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    content = format_solution(res.solution)
                    if res.rejected:
                        content += "\n\n" + format_rejected(res.rejected)
                    out.write_text(content, encoding="utf-8")
                    st.success(f"Exported to {out}")
                else:
                    st.warning("No DFS solution to export.")

    # ── Main content ──────────────────────────────────────────────────
    if st.session_state.problem is None:
        st.info("👈 Upload a JSON file or click **Use Default** to get started.")
        return

    problem = st.session_state.problem
    state = st.session_state.current_state

    # ── Grid visualisation ────────────────────────────────────────────
    st.subheader("📍 Grid View")
    _draw_grid(problem, state)
    st.markdown("")

    # ── State info ────────────────────────────────────────────────────
    st.subheader("📊 Current State")
    _state_info(state, problem)

    if is_goal_state(state):
        st.balloons()
        st.success(f"🎉 Goal reached!  Total cost: **{state.g}**")

    # ── Tabs ──────────────────────────────────────────────────────────
    tab_solution, tab_dfs, tab_tree, tab_manual = st.tabs([
        "📝 Solution (A*)", "🔎 DFS", "🌳 Search Tree", "🎮 Manual Mode"
    ])

    # ── Solution tab ──────────────────────────────────────────────────
    with tab_solution:
        res = st.session_state.solution_result
        if res is None:
            st.info("Click **Run A* Search** in the sidebar.")
        elif not res.success:
            st.warning(
                f"No solution found. Iterations: {res.iterations}, "
                f"Visited: {res.visited_count}, Generated: {res.generated_count}"
            )
        else:
            sol = res.solution
            st.success(f"**Total Cost: {sol.g}**  |  "
                       f"Iterations: {res.iterations}  |  "
                       f"Visited: {res.visited_count}  |  "
                       f"Generated: {res.generated_count}")
            st.markdown("#### Step-by-step solution:")
            for i, act in enumerate(sol.path, 1):
                st.write(f"**{i}.** {act.description}")

            if res.rejected:
                with st.expander(f"⚠️ Rejected Actions ({len(res.rejected)})"):
                    for rec in res.rejected[:50]:
                        st.write(
                            f"- Parent {rec.parent_id} | "
                            f"**{rec.action}** → {rec.reason}"
                        )

    # ── DFS tab ───────────────────────────────────────────────────────
    with tab_dfs:
        res = st.session_state.dfs_result
        if res is None:
            st.info("Click **Run DFS Search** in the sidebar.")
        elif not res.success:
            st.warning(
                f"No DFS solution found. Iterations: {res.iterations}, "
                f"Visited: {res.visited_count}, Generated: {res.generated_count}"
            )
        else:
            sol = res.solution
            st.success(f"**Total Cost: {sol.g}**  |  "
                       f"Iterations: {res.iterations}  |  "
                       f"Visited: {res.visited_count}  |  "
                       f"Generated: {res.generated_count}")
            st.info("Note: DFS does not guarantee the optimal path. It simply returns the first valid solution it encounters.")
            st.markdown("#### Step-by-step solution:")
            for i, act in enumerate(sol.path, 1):
                st.write(f"**{i}.** {act.description}")

            if res.rejected:
                with st.expander(f"⚠️ Rejected Actions ({len(res.rejected)})"):
                    for rec in res.rejected[:50]:
                        st.write(
                            f"- Parent {rec.parent_id} | "
                            f"**{rec.action}** → {rec.reason}"
                        )

    # ── Search-tree tab ───────────────────────────────────────────────
    with tab_tree:
        tr = st.session_state.search_tree
        if tr is None:
            st.info("Click **Generate Search Tree** in the sidebar.")
        else:
            st.code(format_search_tree(tr), language="text")
            if tr.rejected:
                with st.expander(f"⚠️ Tree Rejected Actions ({len(tr.rejected)})"):
                    for rec in tr.rejected[:30]:
                        st.write(
                            f"- Parent {rec.parent_id} | "
                            f"**{rec.action}** → {rec.reason}"
                        )

    # ── Manual-mode tab ───────────────────────────────────────────────
    with tab_manual:
        st.markdown("#### 🕹️ Control the robot manually")
        st.caption(
            "Movement, loading, and unloading use the same validation and action-generation logic as the expert system. "
            "Invalid actions are rejected with an explanation."
        )

        # Movement buttons
        _c1, c_up, _c3 = st.columns([1, 1, 1])
        with c_up:
            if st.button("⬆️ Up"):
                _manual_move(0, -1, "Move Up")
                st.rerun()

        c_left, c_info, c_right = st.columns([1, 1, 1])
        with c_left:
            if st.button("⬅️ Left"):
                _manual_move(-1, 0, "Move Left")
                st.rerun()
        with c_info:
            st.write(f"**{state.robot_pos}**")
        with c_right:
            if st.button("➡️ Right"):
                _manual_move(1, 0, "Move Right")
                st.rerun()

        _c4, c_down, _c6 = st.columns([1, 1, 1])
        with c_down:
            if st.button("⬇️ Down"):
                _manual_move(0, 1, "Move Down")
                st.rerun()

        st.divider()

        # Load button (only at warehouse)
        if state.robot_pos == problem.warehouse:
            st.markdown("##### 📦 Load at Warehouse")
            from expert.engine import FlowerRobotEngine
            engine = FlowerRobotEngine()
            children, rejected, _ = engine.expand_state(state, problem, counter)
            load_children = [c for c in children if c.action.startswith("Load")]
            load_rejected = [r for r in rejected if r.action.startswith("Load")]

            if load_children:
                options = {child.action: child for child in load_children}
                choice = st.selectbox("Choose load:", list(options.keys()))
                if st.button("📥 Load"):
                    st.session_state.current_state = options[choice]
                    st.session_state.manual_log.append(f"✅ {choice}")
                    st.rerun()
            else:
                st.caption("No valid loads available.")
                for rej in load_rejected:
                    st.caption(f"  ❌ {rej.action}: {rej.reason}")
        else:
            st.caption("📦 Load is only available at the warehouse.")

        # Unload button (only at pavilion)
        pav_here = None
        for pav in problem.pavilions:
            if pav.position == state.robot_pos:
                pav_here = pav
                break

        if pav_here:
            st.markdown(f"##### 🌺 Unload at {pav_here.id} ({pav_here.type})")
            counter = st.session_state.manual_counter
            from expert.engine import FlowerRobotEngine
            engine = FlowerRobotEngine()
            children, rejected, _ = engine.expand_state(state, problem, counter)
            unload_children = [c for c in children if c.action.startswith("Unload")]
            unload_rejected = [r for r in rejected if r.action.startswith("Unload")]
            if unload_children:
                options_u = {child.action: child for child in unload_children}
                choice_u = st.selectbox("Choose unload:", list(options_u.keys()))
                if st.button("📤 Unload"):
                    st.session_state.current_state = options_u[choice_u]
                    st.session_state.manual_log.append(f"✅ {choice_u}")
                    st.rerun()
            else:
                st.caption("No valid unloads available.")
                for rej in unload_rejected:
                    st.caption(f"  ❌ {rej.action}: {rej.reason}")
        else:
            st.caption("🌺 Unload is only available at a pavilion.")

        # Manual action log
        if st.session_state.manual_log:
            with st.expander("📜 Manual Action Log"):
                for entry in reversed(st.session_state.manual_log[-30:]):
                    st.write(entry)


if __name__ == "__main__":
    main()
