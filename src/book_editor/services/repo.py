"""Git sync and chapter listing for the editor."""

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


def git_push(
    repo_path: str, token: str, message: str = "Save from Book Editor"
) -> None:
    """Commit changes under Chapters/ and push to origin, using token for HTTPS auth."""
    repo = Repo(repo_path)
    if repo.is_dirty(untracked_files=True):
        repo.git.add("Chapters/")
        repo.index.commit(message)
    origin = repo.remotes.origin
    old_url = origin.url
    if old_url.startswith("https://") and token:
        from urllib.parse import urlparse
        parsed = urlparse(old_url)
        new_url = f"https://{token}@{parsed.netloc}{parsed.path}"
        origin.set_url(new_url)
    try:
        origin.push()
    finally:
        if old_url.startswith("https://") and token:
            origin.set_url(old_url)
