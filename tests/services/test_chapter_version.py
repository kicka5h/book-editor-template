"""Tests for chapter version service."""

import pytest
from pathlib import Path

from book_editor.services.chapter_version import ChapterVersionManager


def test_parse_version():
    manager = ChapterVersionManager("./Chapters")
    assert manager.parse_version("v1.2.3") == (1, 2, 3)
    assert manager.parse_version("1.0.0") == (1, 0, 0)


def test_format_version():
    manager = ChapterVersionManager("./Chapters")
    assert manager.format_version(1, 2, 3) == "v1.2.3"


def test_increment_version():
    manager = ChapterVersionManager("./Chapters")
    assert manager.increment_version((1, 0, 0), "patch") == (1, 0, 1)
    assert manager.increment_version((1, 0, 0), "minor") == (1, 1, 0)
    assert manager.increment_version((1, 0, 0), "major") == (2, 0, 0)


def test_get_latest_version_and_bump(sample_chapters_dir):
    manager = ChapterVersionManager(str(sample_chapters_dir))
    latest = manager.get_latest_version(sample_chapters_dir / "Chapter 1")
    assert latest.name == "v1.0.0"
    md = manager.get_markdown_file(latest)
    assert md.suffix == ".md"

    manager.bump_chapter(1, "minor")
    ch1_dir = sample_chapters_dir / "Chapter 1"
    assert (ch1_dir / "v1.1.0").is_dir()
    assert (ch1_dir / "v1.1.0" / "v1.0.0.md").exists()
