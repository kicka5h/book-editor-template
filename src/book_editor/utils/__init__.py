"""Shared helpers for paths and chapter numbering."""

import re
from pathlib import Path


def chapters_dir(repo_path: str) -> Path:
    """Return the Chapters directory path for a given repo root."""
    return Path(repo_path) / "Chapters"


def chapter_num(name: str) -> int:
    """Extract chapter number from directory name (e.g. 'Chapter 7' -> 7). Returns 0 if no match."""
    m = re.search(r"chapter\s+(\d+)", name, re.I)
    return int(m.group(1)) if m else 0
