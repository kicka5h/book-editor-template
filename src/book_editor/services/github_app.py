"""GitHub API and clone operations for the app (auth, list repos, create repo, clone)."""

import re
from pathlib import Path
from typing import List, Optional, Tuple

from github import Github
from github.GithubException import BadCredentialsException
from git.repo.base import Repo


def validate_token(token: str) -> Optional[str]:
    """
    Validate GitHub token and return the user login, or None if invalid.
    """
    if not (token or "").strip():
        return None
    try:
        g = Github(token.strip())
        user = g.get_user()
        return user.login
    except BadCredentialsException:
        return None
    except Exception:
        return None


def list_user_repos(token: str) -> List[Tuple[str, str, str]]:
    """
    Return list of (owner, name, clone_url) for repos the user has access to (including owned).
    """
    if not (token or "").strip():
        return []
    try:
        g = Github(token.strip())
        user = g.get_user()
        repos = []
        for repo in user.get_repos():
            owner = repo.owner.login
            name = repo.name
            url = repo.clone_url
            repos.append((owner, name, url))
        return repos
    except Exception:
        return []


def create_repo(token: str, name: str, private: bool = False, description: str = "") -> Tuple[str, str, str]:
    """
    Create a new GitHub repository. Returns (owner, name, clone_url).
    """
    g = Github(token.strip())
    user = g.get_user()
    repo = user.create_repo(name, private=private, description=description or "Book content")
    return repo.owner.login, repo.name, repo.clone_url


def clone_repo(clone_url: str, local_path: Path, token: str) -> None:
    """
    Clone the repository to local_path. Uses token for HTTPS auth (inserted into URL).
    """
    from urllib.parse import urlparse
    if token and clone_url.startswith("https://"):
        parsed = urlparse(clone_url)
        auth_url = f"https://{token}@{parsed.netloc}{parsed.path}"
        if parsed.query:
            auth_url += "?" + parsed.query
        Repo.clone_from(auth_url, local_path)
    else:
        Repo.clone_from(clone_url, local_path)


def ensure_chapters_structure(repo_path: Path) -> None:
    """
    If repo has no Chapters/ directory, create it with a starter Chapter 1/v1.0.0/v1.0.0.md.
    """
    chapters_dir = repo_path / "Chapters"
    if chapters_dir.exists() and chapters_dir.is_dir():
        return
    chapters_dir.mkdir(parents=True)
    ch1 = chapters_dir / "Chapter 1" / "v1.0.0"
    ch1.mkdir(parents=True)
    (ch1 / "v1.0.0.md").write_text("# Chapter 1\n\n", encoding="utf-8")
