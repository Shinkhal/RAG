#!/usr/bin/env python3
"""
Windows PowerShell/CMD compatible task runner for the RAG project
Usage: python run.py [command]
"""

import subprocess
import sys
from pathlib import Path

# Virtual environment Python
VENV_PYTHON = ".venv\\Scripts\\python.exe"
BASE_DIR = Path(__file__).parent


def run_command(cmd, description=None):
    """Execute a shell command."""
    if description:
        print(f"\n📦 {description}...")
    try:
        result = subprocess.run(cmd, shell=True, cwd=BASE_DIR)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main task runner."""
    commands = {
        "help": lambda: print_help(),
        "install": lambda: run_command(
            f"{VENV_PYTHON} -m pip install -r requirements.txt",
            "Installing dependencies"
        ),
        "run": lambda: run_command(
            f"{VENV_PYTHON} -m uvicorn app.main:app --reload",
            "Starting FastAPI server"
        ),
        "test": lambda: run_command(
            f"{VENV_PYTHON} -m pytest -q",
            "Running tests"
        ),
        "lint": lambda: run_command(
            f"{VENV_PYTHON} -m ruff check .",
            "Running linter"
        ),
        "format": lambda: run_command(
            f"{VENV_PYTHON} -m ruff format .",
            "Formatting code"
        ),
        "typecheck": lambda: run_command(
            f"{VENV_PYTHON} -m mypy app",
            "Type checking"
        ),
    }

    cmd = sys.argv[1].lower() if len(sys.argv) > 1 else "help"

    if cmd == "check":
        run_command(f"{VENV_PYTHON} -m ruff check .", "Running linter")
        run_command(f"{VENV_PYTHON} -m mypy app", "Type checking")
        run_command(f"{VENV_PYTHON} -m pytest -q", "Running tests")
        return

    if cmd in commands:
        commands[cmd]()
    else:
        print(f"❌ Unknown command: {cmd}")
        print_help()
        sys.exit(1)


def print_help():
    """Print available commands."""
    print("""
📚 RAG Project Task Runner
Usage: python run.py [command]

Available commands:
  help       Show this help message
  install    Install dependencies from requirements.txt
  run        Start FastAPI app with reload
  test       Run pytest
  lint       Run ruff checks
  format     Format code with ruff
  typecheck  Run mypy on app/
  check      Run lint + typecheck + test (sequentially)

Examples:
  python run.py install
  python run.py run
  python run.py test
    """)


if __name__ == "__main__":
    main()

