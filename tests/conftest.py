"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path


@pytest.fixture
def sample_chapters_dir(tmp_path):
    """Create a minimal Chapters/ structure (Chapter 1/v1.0.0/file.md)."""
    ch1 = tmp_path / "Chapter 1" / "v1.0.0"
    ch1.mkdir(parents=True)
    (ch1 / "v1.0.0.md").write_text("# Chapter 1\n\n", encoding="utf-8")
    return tmp_path
