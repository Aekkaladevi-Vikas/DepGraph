"""
crawler.py — Walks the project directory and collects all Python source files.
"""

from pathlib import Path
from typing import List


EXCLUDE_DIRS = {
    "__pycache__", ".git", ".hg", ".svn", ".tox",
    "venv", ".venv", "env", ".env",
    "node_modules", "dist", "build", ".eggs",
    "*.egg-info", "site-packages", "migrations",
}


def crawl_project(root: str) -> List[Path]:
    """
    Recursively walk a project directory and return all .py file paths.

    Args:
        root: Path to the root of the Python project.

    Returns:
        List of Path objects pointing to .py files.
    """
    root_path = Path(root).resolve()

    if not root_path.exists():
        raise FileNotFoundError(f"Project path does not exist: {root_path}")

    if not root_path.is_dir():
        raise NotADirectoryError(f"Expected a directory, got: {root_path}")

    py_files = []

    for path in root_path.rglob("*.py"):
        # Skip excluded directories
        if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
            continue
        # Skip hidden directories
        if any(part.startswith(".") for part in path.parts[len(root_path.parts):]):
            continue
        py_files.append(path)

    return sorted(py_files)