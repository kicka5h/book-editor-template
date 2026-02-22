"""App config stored in platform config directory on the user's machine."""

import json
import os
import sys
from pathlib import Path


def config_dir() -> Path:
    """Return the platform-specific config directory for this app."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return Path(base) / "beckit"


def config_file() -> Path:
    return config_dir() / "config.json"


def load_config() -> dict:
    """Load full config. Keys: github_token, github_user, repo_owner, repo_name, repo_url, local_repo_path (legacy: repo_path)."""
    p = config_file()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config_full(config: dict) -> None:
    """Persist full config dict (overwrites)."""
    config_dir().mkdir(parents=True, exist_ok=True)
    with open(config_file(), "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def save_github_connection(token: str, github_user: str) -> None:
    """Save GitHub token and username; keep existing repo/local path if any."""
    cfg = load_config()
    cfg["github_token"] = token
    cfg["github_user"] = github_user
    save_config_full(cfg)


def save_repo_selection(repo_owner: str, repo_name: str, repo_url: str, local_repo_path: str) -> None:
    """Save selected repo and local clone path."""
    cfg = load_config()
    cfg["repo_owner"] = repo_owner
    cfg["repo_name"] = repo_name
    cfg["repo_url"] = repo_url
    cfg["local_repo_path"] = local_repo_path
    cfg["repo_path"] = local_repo_path  # legacy key for editor
    save_config_full(cfg)


def is_github_connected(config: dict = None) -> bool:
    """True if we have a stored GitHub token."""
    cfg = config if config is not None else load_config()
    return bool((cfg.get("github_token") or "").strip())


def has_repo_selected(config: dict = None) -> bool:
    """True if we have a repo and local path."""
    cfg = config if config is not None else load_config()
    path = (cfg.get("local_repo_path") or cfg.get("repo_path") or "").strip()
    return bool(path)


def get_repo_path(config: dict = None) -> str:
    """Return local repo path for the editor (legacy repo_path or local_repo_path)."""
    cfg = config if config is not None else load_config()
    return (cfg.get("local_repo_path") or cfg.get("repo_path") or "").strip()
