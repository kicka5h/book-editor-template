"""GitHub API and clone operations for the app (auth, list repos, create repo, clone)."""

import os
import time
from pathlib import Path
from typing import Callable, List, Optional, Tuple

import requests
from github import Auth, Github
from github.GithubException import BadCredentialsException
from git.repo.base import Repo

_DEVICE_CODE_URL = "https://github.com/login/device/code"
_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token"
_DEVICE_GRANT_TYPE = "urn:ietf:params:oauth:grant-type:device_code"


# Client ID for the Beckit GitHub OAuth App.
# This is NOT a secret — device flow requires no client secret.
# Register your own OAuth App at github.com/settings/developers if forking.
# Override at runtime by setting the GITHUB_CLIENT_ID environment variable.
_OAUTH_CLIENT_ID = "Ov23ligmSNv1BbiCocZi"


def _client_id() -> str:
    return os.environ.get("GITHUB_CLIENT_ID", _OAUTH_CLIENT_ID).strip()


def start_device_flow() -> dict:
    """
    Begin the device flow.  Returns the full response dict containing:
      device_code, user_code, verification_uri, expires_in, interval
    Raises RuntimeError on failure.
    """
    resp = requests.post(
        _DEVICE_CODE_URL,
        headers={"Accept": "application/json"},
        json={"client_id": _client_id(), "scope": "repo"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(data.get("error_description", data["error"]))
    return data


def poll_device_flow(
    device_code: str,
    interval: int,
    expires_in: int,
    on_waiting: Optional[Callable[[], None]] = None,
) -> str:
    """
    Poll until the user authorises the app or the device code expires.
    Calls on_waiting() (if provided) on each authorization_pending response.
    Returns the access token string on success.
    Raises RuntimeError on expiry, denial, or unrecoverable error.
    """
    deadline = time.time() + expires_in
    current_interval = interval

    while time.time() < deadline:
        time.sleep(current_interval)
        resp = requests.post(
            _ACCESS_TOKEN_URL,
            headers={"Accept": "application/json"},
            json={
                "client_id": _client_id(),
                "device_code": device_code,
                "grant_type": _DEVICE_GRANT_TYPE,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if "access_token" in data:
            return data["access_token"]

        error = data.get("error", "")
        if error == "authorization_pending":
            if on_waiting:
                on_waiting()
            continue
        elif error == "slow_down":
            current_interval += 5
            if on_waiting:
                on_waiting()
            continue
        elif error == "access_denied":
            raise RuntimeError("Authorization was denied.")
        elif error == "expired_token":
            raise RuntimeError("Device code expired. Please try again.")
        else:
            raise RuntimeError(data.get("error_description", error))

    raise RuntimeError("Device code expired. Please try again.")


def validate_token(token: str) -> Optional[str]:
    """
    Validate GitHub token and return the user login, or None if invalid.
    """
    if not (token or "").strip():
        return None
    try:
        g = Github(auth=Auth.Token(token.strip()))
        user = g.get_user()
        return user.login
    except BadCredentialsException:
        return None
    except Exception:
        return None


def list_user_repos(token: str) -> List[Tuple[str, str, str]]:
    """
    Return list of (owner, name, clone_url) for repos the user has access to (including owned).
    Raises on network or API errors so callers can surface them to the user.
    """
    if not (token or "").strip():
        return []
    g = Github(auth=Auth.Token(token.strip()))
    user = g.get_user()
    repos = []
    for repo in user.get_repos():
        owner = repo.owner.login
        name = repo.name
        url = repo.clone_url
        repos.append((owner, name, url))
    return repos


def create_repo(token: str, name: str, private: bool = False, description: str = "") -> Tuple[str, str, str]:
    """
    Create a new GitHub repository. Returns (owner, name, clone_url).
    """
    g = Github(auth=Auth.Token(token.strip()))
    user = g.get_user()
    repo = user.create_repo(name, private=private, description=description or "Book content")
    return repo.owner.login, repo.name, repo.clone_url


def clone_repo(clone_url: str, local_path: Path, token: str) -> None:
    """
    Clone the repository to local_path. Uses token for HTTPS auth (inserted into URL).
    After cloning the remote URL is reset to the clean (credential-free) URL so that
    subsequent pushes don't encounter a double-credential malformed URL.
    """
    from urllib.parse import urlparse
    if token and clone_url.startswith("https://"):
        parsed = urlparse(clone_url)
        # Strip any existing credentials from the host, then inject the token
        clean_host = parsed.hostname + (f":{parsed.port}" if parsed.port else "")
        auth_url = f"https://{token}@{clean_host}{parsed.path}"
        if parsed.query:
            auth_url += "?" + parsed.query
        repo = Repo.clone_from(auth_url, local_path)
        # Reset remote URL to credential-free form so it isn't persisted in .git/config
        clean_url = f"https://{clean_host}{parsed.path}"
        if parsed.query:
            clean_url += "?" + parsed.query
        repo.remotes.origin.set_url(clean_url)
    else:
        Repo.clone_from(clone_url, local_path)


def ensure_chapters_structure(repo_path: Path) -> None:
    """
    If repo has no Chapters/ directory, create it with a starter Chapter 1/v1.0.0/v1.0.0.md.
    Also ensures the planning/ directory exists with a starter README.
    """
    from book_editor.services.planning import ensure_planning_structure

    chapters_dir = repo_path / "Chapters"
    if not (chapters_dir.exists() and chapters_dir.is_dir()):
        chapters_dir.mkdir(parents=True)
        ch1 = chapters_dir / "Chapter 1" / "v1.0.0"
        ch1.mkdir(parents=True)
        (ch1 / "v1.0.0.md").write_text("# Chapter 1\n\n", encoding="utf-8")

    ensure_planning_structure(str(repo_path))
