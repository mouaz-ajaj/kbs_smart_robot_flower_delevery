# 🌹 Smart Flower Robot 🤖

**Knowledge-Based Expert System** for a university course on Knowledge-Based Systems.

A robot navigates a grid-based flower exhibition, transporting bouquets from a central warehouse to various pavilions at minimum cost.  
The system uses **Experta** (a Python RETE-based expert system shell) for rule-based reasoning and **A\*** search for optimal path planning.

---

## 📖 Table of Contents

1. [Project Idea](#-project-idea)
2. [State Space Representation](#-state-space-representation)
3. [JSON Input Format](#-json-input-format)
4. [Installation](#-installation)
5. [Running the Project](#-running-the-project)
6. [Movement Rules](#-movement-rules)
7. [Loading Rules](#-loading-rules)
8. [Unloading Rules](#-unloading-rules)
9. [Violation Rules](#-violation-rules)
10. [A\* Search Algorithm](#-a-search-algorithm)
11. [Solution Output Example](#-solution-output-example)
12. [Search Tree Output Example](#-search-tree-output-example)
13. [Manual Mode](#-manual-mode)
14. [Project Structure](#-project-structure)

---

## 🌐 Project Idea

We have a **grid-based flower exhibition** with:

| Entity        | Description |
|---------------|-------------|
| **Grid**      | An `W × H` grid (1-indexed). The robot moves one cell at a time. |
| **Warehouse** | A fixed cell containing unlimited supply of all bouquet types. |
| **Robot**     | Starts at a given cell carrying nothing. |
| **Pavilions** | Each pavilion has a flower type (e.g. Rose) and specific color needs (e.g. Red ×2, Pink ×1). |

**Goal**: Deliver all required bouquets to every pavilion with **minimum total cost** (each move, load, or unload costs 1).

---

## 🧠 State Space Representation

The problem is modelled as a **state-space search** problem:

| Component | Representation |
|-----------|---------------|
| **State** | `(robot_position, current_load, remaining_needs)` |
| **Initial State** | Robot at start, empty load, all needs outstanding |
| **Goal State** | All pavilion needs satisfied AND robot carries nothing |
| **Actions** | Move (4 directions), Load (at warehouse), Unload (at pavilion) |
| **Cost** | Each action costs exactly **1** |
| **Signature** | `(position, frozenset(load), frozenset(needs))` — prevents duplicate states |

### Cost Function

```
f(n) = g(n) + h(n)
```

- **g(n)**: Actual cost from the initial state to state *n* (number of actions taken).
- **h(n)**: Admissible heuristic estimate of remaining cost (see [A\* section](#-a-search-algorithm)).
- **f(n)**: Total estimated cost, used to prioritize states in the open list.

---

## 📄 JSON Input Format

The input is always read from a JSON file (default: `data/initial_state.json`):

```json
{
  "grid": { "width": 5, "height": 5 },
  "warehouse": { "x": 3, "y": 2 },
  "robot": { "x": 1, "y": 3 },
  "flowers": {
    "Rose": ["Red", "Pink", "White", "Yellow", "DarkRed"],
    "Tulip": ["Red", "Yellow", "Purple", "Orange", "Green", "Mauve", "Violet"],
    "Orchid": ["Purple", "White", "Pink", "LightPink"],
    "GoliatRose": ["Gold", "LightPink", "Yellow"]
  },
  "pavilions": [
    {
      "id": "P1", "type": "Rose", "x": 2, "y": 4,
      "needs": { "Red": 2, "Pink": 1, "White": 1 }
    },
    {
      "id": "P2", "type": "Tulip", "x": 4, "y": 3,
      "needs": { "Red": 3, "Yellow": 1 }
    },
    {
      "id": "P3", "type": "Orchid", "x": 4, "y": 5,
      "needs": { "Purple": 2, "Pink": 1 }
    },
    {
      "id": "P4", "type": "GoliatRose", "x": 5, "y": 2,
      "needs": { "Gold": 2, "LightPink": 2 }
    }
  ]
}
```

### Key Fields

| Field | Description |
|-------|-------------|
| `grid.width/height` | Grid dimensions (1-indexed) |
| `warehouse.x/y` | Warehouse position |
| `robot.x/y` | Robot's starting position |
| `flowers` | Mapping: flower type → list of valid colors |
| `pavilions[].id` | Unique pavilion identifier |
| `pavilions[].type` | Flower type this pavilion accepts |
| `pavilions[].needs` | Color → quantity of bouquets needed |

### Validation

The parser automatically:
- Checks all required fields exist
- Validates positions are within grid bounds
- Verifies each pavilion's colors are valid for its flower type
- Computes `max_load` as the largest single-pavilion total need

---

## 🛠 Installation

```bash
# 1. Navigate to the project directory
cd smart_flower_robot

# 2. (Recommended) Create a virtual environment
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
```

> **Note on frozendict**: Experta internally uses `frozendict`.  
> If you encounter import errors on Python 3.11+, try: `pip install frozendict==2.3.8`

---

## 🚀 Running the Project

### Streamlit UI (recommended)

```bash
streamlit run ui/streamlit_app.py
```

This opens a browser interface at `http://localhost:8501` with:
- Grid visualisation
- A\* search execution
- Search tree generation
- Manual control mode
- Export buttons

### CLI Mode

```bash
# Use default JSON
python main.py

# Specify a custom JSON file
python main.py path/to/my_state.json

# Or run the CLI module directly
python -m ui.cli path/to/my_state.json
```

---

## 🚶 Movement Rules

The robot moves **one cell** per action in 4 directions:

| Action | Effect | Condition |
|--------|--------|-----------|
| Move Right | x += 1 | x < grid_width |
| Move Left  | x -= 1 | x > 1 |
| Move Up    | y -= 1 | y > 1 |
| Move Down  | y += 1 | y < grid_height |

- **Cost**: 1 per move
- **Violation**: Moving outside the grid is rejected with a `ViolationFact`
- **Coordinates**: 1-indexed, y increases downward (y=1 is top row)

These are represented as **Experta Rules** that pattern-match on `RobotFact` and `GridFact`:

```python
@Rule(RobotFact(x=MATCH.rx, y=MATCH.ry),
      GridFact(width=MATCH.w),
      TEST(lambda rx, w: rx < w))
def move_right_rule(self, ...):
    ...
```

---

## 📦 Loading Rules

Loading is **only** allowed when the robot is at the **warehouse**.

### Two Options

| Option | Constraint | Example |
|--------|-----------|---------|
| **A** (Same Color) | All bouquets share the same **color**, different flower types OK | `{(Rose, Red): 2, (Tulip, Red): 3}` |
| **B** (Same Type) | All bouquets share the same **flower type**, different colors OK | `{(Rose, Red): 2, (Rose, Pink): 1}` |

### Rules

1. **Location**: Robot must be at warehouse (enforced by Experta MATCH variable joining)
2. **Pattern**: Each load batch must satisfy Option A OR Option B
3. **Max Load**: Total carried ≤ `max_load` (= largest single-pavilion total need)
4. **Relevance**: Only bouquets still needed by some pavilion are loaded
5. **Cost**: 1 per load action (regardless of quantity)

The `load_rule` in Experta uses **MATCH variable joining**:

```python
@Rule(RobotFact(x=MATCH.pos_x, y=MATCH.pos_y),
      WarehouseFact(x=MATCH.pos_x, y=MATCH.pos_y))
def load_rule(self, pos_x, pos_y):
    # pos_x/pos_y match guarantees robot is at warehouse
```

---

## 🌺 Unloading Rules

Unloading is **only** allowed when the robot is at a **pavilion**.

### Critical Constraint: No Partial Unloading

> A color is unloaded **only if** the robot carries **at least** the remaining need for that color.  
> You must unload the **full** remaining need for a color, or not unload it at all.

**Example**: Pavilion P1 needs Red ×2. If the robot carries Red ×1, it **cannot** unload Red at P1. It must carry ≥ 2 Red bouquets.

### Rules

1. **Location**: Robot must be at a pavilion
2. **Type Match**: Only bouquets matching the pavilion's flower type can be unloaded
3. **Minimum Quantity**: Carried quantity ≥ remaining need for that color
4. **No Partial**: All-or-nothing per color
5. **Multi-color**: Multiple eligible colors can be unloaded at once (cost still = 1)
6. **Multiple Visits**: A pavilion can be visited multiple times to receive different colors
7. **Cost**: 1 per unload action (regardless of number of colors/bouquets)

---

## 🚫 Violation Rules

The expert system detects and logs violations:

| Violation | Condition | Experta Rule |
|-----------|-----------|--------------|
| Outside Grid | Move would place robot outside boundaries | `violation_outside_grid_*` |
| Overload | Loading would exceed `max_load` | Checked in `validate_load_batch` |
| Invalid Pattern | Load batch mixes different types AND colors | `is_valid_load_pattern` |
| Invalid Unload | Bouquet type doesn't match pavilion, or quantity < need | `can_unload_color_at_pavilion` |

All violations are asserted as `ViolationFact` and logged with their reason.

---

## 🔍 Search Algorithms

The project implements two search algorithms using the Experta engine (`engine_a_star_search` and `engine_dfs_search`) to navigate the state space.

### 1. A* Search (Optimal)
A* is used to find the **optimal** (lowest cost) path.
1. **Open List**: Min-heap sorted by `f(n) = g(n) + h(n)`
2. **Closed Set**: Set of state signatures (prevents re-expansion)
3. **Expansion**: For each state, the Experta engine fires all applicable rules to generate successors
4. **Goal Test**: All needs satisfied AND robot carries nothing

### 2. Depth-First Search (DFS)
DFS is used to quickly find **a valid solution**, but it does **not** guarantee the optimal path.
1. **Open List**: Stack (LIFO) exploring deep paths first
2. **Closed Set**: Set of state signatures (prevents infinite loops and duplicate states)
3. **Expansion**: Uses the same Experta engine rules
4. **Result**: Usually returns a much longer path with higher cost than A*

### Heuristic h(n) — Components (For A*)

The heuristic is **admissible** (never overestimates), guaranteeing optimal solutions:

| Component | Description |
|-----------|-------------|
| **Warehouse distance** | If robot is empty and needs remain: Manhattan distance to warehouse |
| **Nearest pavilion** | If robot carries useful load: Manhattan distance to nearest benefiting pavilion |
| **Min unloads** | Number of pavilions with remaining needs (each needs ≥ 1 visit) |
| **Min loads** | `⌈remaining_bouquets / max_load⌉` |

### g(n), h(n), f(n)

```
g(n) = actual number of actions from start to state n
h(n) = admissible estimate of remaining actions
f(n) = g(n) + h(n)  ← states with lowest f are expanded first
```

---

## 📋 Solution Output Example

```
Goal reached!

Total cost: 18

Solution path:

  1. Move Right -> robot at (2,3)
  2. Move Right -> robot at (3,3)
  3. Move Up -> robot at (3,2)
  4. Load [Rose Red x2, Rose Pink x1, Rose White x1]
  5. Move Left -> robot at (2,2)
  6. Move Down -> robot at (2,3)
  7. Move Down -> robot at (2,4)
  8. Unload at P1 [Rose Red x2, Rose Pink x1, Rose White x1]
  ...
```

---

## 🌳 Search Tree Output Example

```
State 0
  robot=(1,3), load={}, g=0, h=10.0, f=10.0
├── State 1 via Move Right -> robot at (2,3)
│     robot=(2,3), load={}, g=1, h=9.0, f=10.0
│   ├── State 5 via Move Right -> robot at (3,3)
│   │     robot=(3,3), load={}, g=2, h=8.0, f=10.0
│   └── State 6 via Move Down -> robot at (2,4)
│         robot=(2,4), load={}, g=2, h=9.0, f=11.0
├── State 2 via Move Down -> robot at (1,4)
│     robot=(1,4), load={}, g=1, h=10.0, f=11.0
└── State 3 via Move Up -> robot at (1,2)
      robot=(1,2), load={}, g=1, h=9.0, f=10.0
```

The tree shows parent-child relationships with box-drawing characters.

---

## 🎮 Manual Mode

In the Streamlit UI, the **Manual Mode** tab allows interactive robot control:

| Control | Description |
|---------|-------------|
| ⬆️ ⬇️ ⬅️ ➡️ | Directional movement buttons |
| 📥 Load | Available when robot is at warehouse; shows a dropdown of valid load options |
| 📤 Unload | Available when robot is at a pavilion; shows valid unload options |
| 🔄 Reset | Resets to initial state |

**Important**: Manual mode does **not** contain its own decision logic. All validity checks go through the same rules engine and validators used by A\*, ensuring consistency.

---

## 📁 Project Structure

```
smart_flower_robot/
│
├── main.py                 # Entry point (CLI + usage info)
├── requirements.txt        # Python dependencies
├── README.md               # This file
│
├── data/
│   └── initial_state.json  # Default problem input
│
├── core/
│   ├── models.py           # Dataclasses: Position, Pavilion, Problem, State, Action
│   ├── parser.py           # JSON loading, validation, Problem construction
│   ├── validators.py       # Pure validation predicates
│   ├── actions.py          # Successor-state generation (moves, loads, unloads)
│   ├── heuristics.py       # Manhattan distance + admissible heuristic
│   └── search.py           # A* algorithm + search tree generation + formatters
│
├── expert/
│   ├── facts.py            # Experta Fact definitions (GridFact, RobotFact, etc.)
│   └── engine.py           # FlowerRobotEngine with 13 Rules + engine-based A*
│
├── ui/
│   ├── streamlit_app.py    # Browser UI (grid view, A*, manual mode, export)
│   └── cli.py              # Command-line interface
│
└── output/
    ├── solution.txt         # Generated solution (after running A*)
    └── search_tree.txt      # Generated search tree
```

---

## 🔑 Design Decisions

1. **Rules delegate to functions**: Experta Rules call clean functions in `core/actions.py` and `core/validators.py` rather than embedding all logic in the rules themselves. This keeps the knowledge representation declarative while maintaining readable, testable code.

2. **State signature for duplicate detection**: A state's identity is `(position, load, remaining_needs)` — the path taken doesn't matter for duplicate detection, only the current situation.

3. **Load generation strategy**: Loads are generated by targeting specific pavilion needs (per-pavilion subsets and cross-pavilion combinations), avoiding combinatorial explosion while giving A\* enough options to find the optimal solution.

4. **Admissible heuristic**: The heuristic never overestimates the true remaining cost, guaranteeing that A\* finds the **optimal** solution.

5. **Search Algorithms Integration**: Both A* and DFS share the exact same state expansion logic (`FlowerRobotEngine`), ensuring consistency across algorithms while highlighting the differences between optimal (A*) and non-optimal (DFS) search strategies.

---

*Built for a Knowledge-Based Systems university course.*
