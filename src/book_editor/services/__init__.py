"""Services: chapter versioning, create chapter, increment chapters, word count, format, git sync, GitHub app, PDF build."""

from book_editor.services.chapter_version import ChapterVersionManager
from book_editor.services.create_chapter import create_new_chapter
from book_editor.services.increment_chapters import increment_chapters
from book_editor.services.count_chapter_words import find_latest_versions, count_words_in_chapters
from book_editor.services.format_markdown import format_markdown, process_file
from book_editor.services.repo import git_push, list_chapters_with_versions
from book_editor.services.github_app import (
    validate_token,
    list_user_repos,
    create_repo,
    clone_repo,
    ensure_chapters_structure,
    start_device_flow,
    poll_device_flow,
)
from book_editor.services.pdf_build import build_pdf, get_latest_chapter_files, check_pandoc_available

__all__ = [
    "ChapterVersionManager",
    "create_new_chapter",
    "increment_chapters",
    "find_latest_versions",
    "count_words_in_chapters",
    "format_markdown",
    "process_file",
    "git_push",
    "list_chapters_with_versions",
    "validate_token",
    "list_user_repos",
    "create_repo",
    "clone_repo",
    "ensure_chapters_structure",
    "start_device_flow",
    "poll_device_flow",
    "build_pdf",
    "get_latest_chapter_files",
    "check_pandoc_available",
]
