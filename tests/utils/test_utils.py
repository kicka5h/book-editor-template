"""Tests for utils (paths, chapter number extraction)."""

from pathlib import Path

from book_editor.utils import chapters_dir, chapter_num


def test_chapters_dir():
    assert chapters_dir("/repo") == Path("/repo/Chapters")
    assert chapters_dir("/home/user/book") == Path("/home/user/book/Chapters")


def test_chapter_num():
    assert chapter_num("Chapter 1") == 1
    assert chapter_num("Chapter 42") == 42
    assert chapter_num("chapter 7") == 7
    assert chapter_num("other") == 0
