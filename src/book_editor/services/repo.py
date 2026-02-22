"""Git sync and chapter listing for the editor."""

from __future__ import annotations

import shutil
from pathlib import Path

from git.repo.base import Repo

from book_editor.services.chapter_version import ChapterVersionManager
from book_editor.utils import chapters_dir as _chapters_dir, chapter_num


def list_chapters_with_versions(repo_path: str) -> list:
    """Return list of (chapter_num, version_str, path_to_md_file) for the given repo."""
    cdir = _chapters_dir(repo_path)
    if not cdir.exists():
        return []
    manager = ChapterVersionManager(str(cdir))
    result = []
    for item in sorted(cdir.iterdir(), key=lambda x: chapter_num(x.name)):
        if not item.is_dir() or not item.name.lower().startswith("chapter "):
            continue
        num = chapter_num(item.name)
        try:
            latest = manager.get_latest_version(item)
            md = manager.get_markdown_file(latest)
            result.append((num, latest.name, md))
        except Exception:
            continue
    return result


def delete_chapter(repo_path: str, chapter_num_to_delete: int) -> None:
    """
    Delete the Chapter folder for the given chapter number and renumber all
    higher chapters downward so there are no gaps.

    e.g. deleting Chapter 3 from [1,2,3,4,5] produces [1,2,3,4].
    """
    cdir = _chapters_dir(repo_path)
    target = cdir / f"Chapter {chapter_num_to_delete}"
    if not target.exists():
        raise FileNotFoundError(f"Chapter {chapter_num_to_delete} not found at {target}")

    shutil.rmtree(target)

    # Renumber higher chapters downward to close the gap
    chapters = sorted(
        [
            (chapter_num(d.name), d)
            for d in cdir.iterdir()
            if d.is_dir() and chapter_num(d.name) > chapter_num_to_delete
        ],
        key=lambda t: t[0],
    )
    for num, directory in chapters:
        new_name = f"Chapter {num - 1}"
        directory.rename(directory.parent / new_name)


def reorder_chapters(repo_path: str, new_order: list) -> None:
    """
    Reorder chapters to match new_order, a list of current chapter numbers in
    the desired sequence.  e.g. [1, 3, 2, 4] swaps chapters 2 and 3.

    Uses a temporary-name shuffle to avoid collisions during renaming.
    """
    cdir = _chapters_dir(repo_path)

    # Step 1 — rename every chapter to a temp name so we can freely reassign numbers
    tmp_dirs = {}
    for i, old_num in enumerate(new_order):
        src = cdir / f"Chapter {old_num}"
        if not src.exists():
            raise FileNotFoundError(f"Chapter {old_num} not found")
        tmp = cdir / f"__tmp_chapter_{i}__"
        src.rename(tmp)
        tmp_dirs[i] = tmp

    # Step 2 — rename each temp dir to its new chapter number (1-based position)
    for i, tmp in sorted(tmp_dirs.items()):
        final = cdir / f"Chapter {i + 1}"
        tmp.rename(final)


def git_push(
    repo_path: str, token: str, message: str = "Save from Beckit"
) -> None:
    """Commit changes under Chapters/ and push to origin, using token for HTTPS auth."""
    repo = Repo(repo_path)
    if repo.is_dirty(untracked_files=True):
        repo.git.add("Chapters/")
        # Also stage planning notes if present
        planning = Path(repo_path) / "planning"
        if planning.exists():
            repo.git.add("planning/")
        repo.index.commit(message)
    origin = repo.remotes.origin
    old_url = origin.url
    if old_url.startswith("https://") and token:
        from urllib.parse import urlparse
        parsed = urlparse(old_url)
        # Use parsed.hostname (strips any embedded credentials) rather than
        # parsed.netloc, which may contain an old "user:pass@" prefix and would
        # produce a malformed URL like https://newtoken@oldtoken@github.com/...
        clean_host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        new_url = f"https://{token}@{clean_host}{parsed.path}"
        origin.set_url(new_url)
    try:
        origin.push()
    finally:
        if old_url.startswith("https://") and token:
            origin.set_url(old_url)
