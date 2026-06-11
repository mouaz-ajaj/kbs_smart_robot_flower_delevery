"""
main.py
=======
Entry point for the Smart Flower Robot project.

Usage:
    # Run the Streamlit UI (recommended):
    streamlit run ui/streamlit_app.py

    # Run the CLI:
    python main.py                              # uses default JSON
    python main.py data/initial_state.json      # specify JSON path

    # Or run the CLI module directly:
    python -m ui.cli [path/to/json]
"""

import sys
from pathlib import Path

# Ensure project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    print()
    print("  +===============================================+")
    print("  |   Smart Flower Robot                          |")
    print("  |   Knowledge-Based Expert System               |")
    print("  +===============================================+")
    print()
    print("  To launch the Streamlit UI (recommended):")
    print("    streamlit run ui/streamlit_app.py")
    print()
    print("  Running CLI mode now...")
    print()

    from ui.cli import run_cli

    json_path = sys.argv[1] if len(sys.argv) > 1 else None
    run_cli(json_path)


if __name__ == "__main__":
    main()
